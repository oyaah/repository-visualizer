from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from app.models import FileMetrics

IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    ".vite",
    "target",
}

SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
}

BRANCH_TOKENS = {
    "if",
    "elif",
    "else",
    "for",
    "while",
    "case",
    "catch",
    "except",
    "switch",
    "&&",
    "||",
    "?",
}


@dataclass(frozen=True)
class ScannedFile:
    path: Path
    relative_path: str
    folder: str
    extension: str
    text: str
    metrics: FileMetrics


def scan_repository(root: Path) -> tuple[list[ScannedFile], list[str]]:
    root = root.resolve()
    ignored_seen: set[str] = set()
    files: list[ScannedFile] = []

    for current_root, directory_names, file_names in os.walk(root):
        ignored_here = sorted(set(directory_names) & IGNORED_DIRECTORIES)
        ignored_seen.update(ignored_here)
        directory_names[:] = sorted(name for name in directory_names if name not in IGNORED_DIRECTORIES)

        for file_name in sorted(file_names):
            path = Path(current_root) / file_name
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            relative = path.relative_to(root).as_posix()
            folder = path.relative_to(root).parent.as_posix()
            files.append(
                ScannedFile(
                    path=path,
                    relative_path=relative,
                    folder="" if folder == "." else folder,
                    extension=path.suffix.lower(),
                    text=text,
                    metrics=calculate_metrics(text, path.stat().st_size),
                )
            )

    return files, sorted(ignored_seen)


def calculate_metrics(text: str, size_bytes: int) -> FileMetrics:
    lines = text.splitlines()
    meaningful = [line for line in lines if line.strip()]
    complexity = 1
    for line in meaningful:
        stripped = line.strip()
        tokens = stripped.replace("(", " ").replace(")", " ").replace(":", " ").split()
        complexity += sum(1 for token in tokens if token in BRANCH_TOKENS)
        complexity += stripped.count("&&") + stripped.count("||")
    return FileMetrics(
        loc=len(meaningful),
        total_lines=len(lines),
        size_bytes=size_bytes,
        complexity=complexity,
    )
