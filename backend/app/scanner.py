from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fnmatch import fnmatch
import math
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
    skipped_reasons: dict[str, int]
    truncated: bool
    warnings: list[str]


@dataclass(frozen=True)
class IgnoreRule:
    pattern: str
    directory_only: bool
    anchored: bool
    negated: bool


def scan_repository(root: Path, options: AnalyzeRequest | None = None) -> ScanResult:
    root = root.resolve()
    options = options or AnalyzeRequest(root_path=str(root))
    ignored_seen: set[str] = set()
    skipped_reasons: Counter[str] = Counter()
    ignore_rules = load_gitignore_rules(root)
    candidates: list[Path] = []
    files: list[ScannedFile] = []

    for current_root, directory_names, file_names in os.walk(root):
        ignored_names = set(IGNORED_DIRECTORIES)
        if not options.include_vendor:
            ignored_names |= VENDOR_DIRECTORIES
        if not options.include_tests:
            ignored_names |= TEST_DIRECTORIES

        kept_directories = []
        for name in sorted(directory_names):
            relative_dir = (Path(current_root) / name).relative_to(root).as_posix()
            if name in ignored_names:
                ignored_seen.add(name)
                continue
            if is_gitignored(relative_dir, is_dir=True, rules=ignore_rules):
                ignored_seen.add(relative_dir)
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories

        for file_name in sorted(file_names):
            path = Path(current_root) / file_name
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            relative_path = path.relative_to(root).as_posix()
            if is_gitignored(relative_path, is_dir=False, rules=ignore_rules):
                skipped_reasons["gitignore"] += 1
                continue
            if should_skip_file(path, root, options):
                skipped_reasons["scan_policy"] += 1
                continue
            candidates.append(path)

    total_files_found = len(candidates) + sum(skipped_reasons.values())
    truncated = len(candidates) > options.max_files
    selected = candidates[: options.max_files]

    for path in selected:
        try:
            text = path.read_text(encoding="utf-8")
            size_bytes = path.stat().st_size
        except (OSError, UnicodeDecodeError):
            skipped_reasons["unreadable"] += 1
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
        skipped_reasons["max_files"] += len(candidates) - len(selected)

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
        skipped_files=sum(skipped_reasons.values()),
        skipped_reasons=dict(sorted(skipped_reasons.items())),
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


def load_gitignore_rules(root: Path) -> list[IgnoreRule]:
    gitignore = root / ".gitignore"
    try:
        lines = gitignore.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    rules: list[IgnoreRule] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        directory_only = line.endswith("/")
        pattern = line.rstrip("/")
        anchored = pattern.startswith("/")
        pattern = pattern.lstrip("/")
        if pattern:
            rules.append(IgnoreRule(pattern=pattern, directory_only=directory_only, anchored=anchored, negated=negated))
    return rules


def is_gitignored(relative_path: str, is_dir: bool, rules: list[IgnoreRule]) -> bool:
    normalized = relative_path.strip("/")
    name = Path(normalized).name
    ignored = False
    for rule in rules:
        if rule.directory_only and not is_dir:
            continue
        matches = False
        if rule.anchored and fnmatch(normalized, rule.pattern):
            matches = True
        elif "/" in rule.pattern and fnmatch(normalized, rule.pattern):
            matches = True
        elif "/" not in rule.pattern and (fnmatch(name, rule.pattern) or any(fnmatch(part, rule.pattern) for part in normalized.split("/"))):
            matches = True
        if matches:
            ignored = not rule.negated
    return ignored


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
        maintainability=calculate_maintainability(len(meaningful), complexity, size_bytes),
    )


def calculate_maintainability(loc: int, complexity: int, size_bytes: int) -> float:
    if loc <= 0:
        return 100.0
    volume = max(size_bytes * 8, 1)
    score = 171.0 - (5.2 * math.log(volume)) - (0.23 * complexity) - (16.2 * math.log(loc))
    return round(max(0.0, min(100.0, score)), 2)
