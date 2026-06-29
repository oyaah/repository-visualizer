from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx

from app.cache import SummaryCache
from app.models import SummaryResponse

PROMPT_VERSION = "repo-risk-summary-v2"
MAX_SUMMARY_CHARS = 20_000
OPENAI_PROVIDER = "openai"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


class SummaryService:
    def __init__(self, cache: SummaryCache) -> None:
        self.cache = cache

    async def summarize(self, root: Path, file_path: str, model: str | None = None, cache_only: bool = False) -> SummaryResponse:
        target = safe_join(root, file_path)
        if not target.exists() or not target.is_file():
            raise ValueError("file_path must point to a file inside root_path")

        text = target.read_text(encoding="utf-8", errors="replace")
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        model_name = model or DEFAULT_OPENAI_MODEL
        key = cache_key(file_path, content_hash, model_name)
        cached = self.cache.get(key)
        if cached:
            return SummaryResponse(
                file_path=file_path,
                summary=cached.summary,
                cached=True,
                content_hash=content_hash,
                model=model_name,
            )

        disabled_reason = disabled_ai_reason()
        if cache_only:
            if disabled_reason:
                return SummaryResponse(
                    file_path=file_path,
                    summary=None,
                    cached=False,
                    disabled=True,
                    error=disabled_reason,
                    content_hash=content_hash,
                    model=model_name,
                )
            return SummaryResponse(
                file_path=file_path,
                summary=None,
                cached=False,
                requires_generation=True,
                error="No cached summary yet. Generate one to analyze this file.",
                content_hash=content_hash,
                model=model_name,
            )

        if len(text) > MAX_SUMMARY_CHARS:
            text = text[:MAX_SUMMARY_CHARS] + "\n\n[truncated for summary]"

        if disabled_reason:
            return SummaryResponse(
                file_path=file_path,
                summary=None,
                cached=False,
                disabled=True,
                error=disabled_reason,
                content_hash=content_hash,
                model=model_name,
            )

        prompt = build_summary_prompt(file_path, text)
        try:
            summary = await call_openai(model_name, prompt)
        except httpx.HTTPError as exc:
            return SummaryResponse(
                file_path=file_path,
                summary=None,
                cached=False,
                error=f"OpenAI request failed: {exc}",
                content_hash=content_hash,
                model=model_name,
            )

        self.cache.set(key, file_path, content_hash, PROMPT_VERSION, model_name, summary, OPENAI_PROVIDER)
        return SummaryResponse(
            file_path=file_path,
            summary=summary,
            cached=False,
            content_hash=content_hash,
            model=model_name,
        )


def safe_join(root: Path, file_path: str) -> Path:
    root = root.resolve()
    target = (root / file_path).resolve()
    if root != target and root not in target.parents:
        raise ValueError("file_path must stay inside root_path")
    return target


def cache_key(file_path: str, content_hash: str, model: str) -> str:
    raw = f"{file_path}:{content_hash}:{PROMPT_VERSION}:{OPENAI_PROVIDER}:{model}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_summary_prompt(file_path: str, text: str) -> str:
    return (
        "Explain this file for a developer onboarding to the repository.\n"
        "Return exactly four short bullets with these labels:\n"
        "- Purpose: what this file is responsible for.\n"
        "- Key dependencies: important imports, includes, or collaborators visible in the code.\n"
        "- Change risk: what could break if this file changes.\n"
        "- Read next: the next file or concept to inspect, if one is visible.\n\n"
        f"File: {file_path}\n\n{text}"
    )


def disabled_ai_reason() -> str | None:
    if not os.getenv("OPENAI_API_KEY"):
        return "Set OPENAI_API_KEY to enable OpenAI summaries."
    return None


async def call_openai(model: str, prompt: str) -> str:
    api_key = os.environ["OPENAI_API_KEY"]
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "input": prompt},
        )
        response.raise_for_status()
    data = response.json()
    if "output_text" in data:
        return data["output_text"].strip()
    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "\n".join(parts).strip() or "No summary returned."
