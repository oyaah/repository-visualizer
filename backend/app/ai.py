from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx

from app.cache import SummaryCache
from app.models import SummaryResponse

PROMPT_VERSION = "explain-3-sentences-v1"
MAX_SUMMARY_CHARS = 20_000


class SummaryService:
    def __init__(self, cache: SummaryCache) -> None:
        self.cache = cache

    async def summarize(self, root: Path, file_path: str, provider: str, model: str | None = None) -> SummaryResponse:
        target = safe_join(root, file_path)
        if not target.exists() or not target.is_file():
            raise ValueError("file_path must point to a file inside root_path")

        text = target.read_text(encoding="utf-8", errors="replace")
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        provider_name = provider.lower()
        model_name = model or default_model(provider_name)
        key = cache_key(file_path, content_hash, provider_name, model_name)
        cached = self.cache.get(key)
        if cached:
            return SummaryResponse(
                file_path=file_path,
                summary=cached.summary,
                cached=True,
                content_hash=content_hash,
                provider=provider_name,
                model=model_name,
            )

        if len(text) > MAX_SUMMARY_CHARS:
            text = text[:MAX_SUMMARY_CHARS] + "\n\n[truncated for summary]"

        disabled_reason = disabled_ai_reason(provider_name)
        if disabled_reason:
            return SummaryResponse(
                file_path=file_path,
                summary=None,
                cached=False,
                disabled=True,
                error=disabled_reason,
                content_hash=content_hash,
                provider=provider_name,
                model=model_name,
            )

        prompt = f"Explain what this code does in 3 simple sentences.\n\nFile: {file_path}\n\n{text}"
        try:
            summary = await call_provider(provider_name, model_name, prompt)
        except httpx.HTTPError as exc:
            return SummaryResponse(
                file_path=file_path,
                summary=None,
                cached=False,
                error=f"AI provider request failed: {exc}",
                content_hash=content_hash,
                provider=provider_name,
                model=model_name,
            )

        self.cache.set(key, file_path, content_hash, PROMPT_VERSION, provider_name, model_name, summary)
        return SummaryResponse(
            file_path=file_path,
            summary=summary,
            cached=False,
            content_hash=content_hash,
            provider=provider_name,
            model=model_name,
        )


def safe_join(root: Path, file_path: str) -> Path:
    root = root.resolve()
    target = (root / file_path).resolve()
    if root != target and root not in target.parents:
        raise ValueError("file_path must stay inside root_path")
    return target


def default_model(provider: str) -> str:
    if provider == "gemini":
        return "gemini-2.5-flash"
    return "gpt-4.1-mini"


def cache_key(file_path: str, content_hash: str, provider: str, model: str) -> str:
    raw = f"{file_path}:{content_hash}:{PROMPT_VERSION}:{provider}:{model}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def disabled_ai_reason(provider: str) -> str | None:
    if provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        return "Set GEMINI_API_KEY to enable Gemini summaries."
    if provider != "gemini" and not os.getenv("OPENAI_API_KEY"):
        return "Set OPENAI_API_KEY to enable OpenAI summaries."
    return None


async def call_provider(provider: str, model: str, prompt: str) -> str:
    if provider == "gemini":
        return await call_gemini(model, prompt)
    return await call_openai(model, prompt)


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


async def call_gemini(model: str, prompt: str) -> str:
    api_key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
        response.raise_for_status()
    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        return "No summary returned."
    parts = candidates[0].get("content", {}).get("parts", [])
    return "\n".join(part.get("text", "") for part in parts).strip() or "No summary returned."

