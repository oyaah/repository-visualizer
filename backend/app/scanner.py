from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from app.models import AnalyzeRequest, FileMetrics

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

VENDOR_DIRECTORIES = {
    "vendor",
    "vendors",
    "third_party",
    "third-party",
    "bower_components",
}

TEST_DIRECTORIES = {
    "__tests__",
    "spec",
    "specs",
    "test",
    "tests",
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


@dataclass(frozen=True)
class ScanResult:
    files: list[ScannedFile]
    ignored_directories: list[str]
    total_files_found: int
    skipped_files: int
    truncated: bool
    warnings: list[str]


def scan_repository(root: Path, options: AnalyzeRequest | None = None) -> ScanResult:
    root = root.resolve()
    options = options or AnalyzeRequest(root_path=str(root))
    ignored_seen: set[str] = set()
    skipped_files = 0
    candidates: list[Path] = []
    files: list[ScannedFile] = []

    for current_root, directory_names, file_names in os.walk(root):
        ignored_names = set(IGNORED_DIRECTORIES)
        if not options.include_vendor:
            ignored_names |= VENDOR_DIRECTORIES
        if not options.include_tests:
            ignored_names |= TEST_DIRECTORIES

        ignored_here = sorted(set(directory_names) & ignored_names)
        ignored_seen.update(ignored_here)
        directory_names[:] = sorted(name for name in directory_names if name not in ignored_names)

        for file_name in sorted(file_names):
            path = Path(current_root) / file_name
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if should_skip_file(path, root, options):
                skipped_files += 1
                continue
            candidates.append(path)

    total_files_found = len(candidates) + skipped_files
    truncated = len(candidates) > options.max_files
    selected = candidates[: options.max_files]

    for path in selected:
        try:
            text = path.read_text(encoding="utf-8")
            size_bytes = path.stat().st_size
        except (OSError, UnicodeDecodeError):
            skipped_files += 1
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
                metrics=calculate_metrics(text, size_bytes),
            )
        )

    if truncated:
        skipped_files += len(candidates) - len(selected)

    warnings = []
    if truncated:
        warnings.append(f"Analysis limited to {options.max_files} files out of {len(candidates)} eligible files.")
    if not options.include_vendor:
        warnings.append("Vendor and generated-looking files are excluded by default.")
    if not options.include_tests:
        warnings.append("Test files are excluded from this scan.")

    return ScanResult(
        files=files,
        ignored_directories=sorted(ignored_seen),
        total_files_found=total_files_found,
        skipped_files=skipped_files,
        truncated=truncated,
        warnings=warnings,
    )


def should_skip_file(path: Path, root: Path, options: AnalyzeRequest) -> bool:
    relative = path.relative_to(root)
    parts = {part.lower() for part in relative.parts[:-1]}
    name = path.name.lower()

    if not options.include_vendor and is_vendor_like(parts, name):
        return True
    if not options.include_tests and is_test_like(parts, name):
        return True
    return False


def is_vendor_like(parts: set[str], name: str) -> bool:
    if parts & VENDOR_DIRECTORIES:
        return True
    return name.endswith((".min.js", ".bundle.js", ".generated.py", ".generated.ts", ".generated.tsx"))


def is_test_like(parts: set[str], name: str) -> bool:
    if parts & TEST_DIRECTORIES:
        return True
    stem = Path(name).stem
    return name.startswith("test_") or stem.endswith("_test") or stem.endswith(".test") or stem.endswith(".spec")


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
