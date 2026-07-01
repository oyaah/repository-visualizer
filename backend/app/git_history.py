from __future__ import annotations

import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Bound history so huge repos stay responsive. Newest commits matter most for
# churn and ownership, so we read the most recent slice and flag when capped.
DEFAULT_COMMIT_CAP = 1500
GIT_TIMEOUT_SECONDS = 30
RECORD_SEPARATOR = "\x1e"
UNIT_SEPARATOR = "\x1f"
FIX_PATTERN = re.compile(r"\b(fix|fixes|fixed|bug|bugfix|hotfix|patch|regression|revert)\b", re.IGNORECASE)


@dataclass
class FileHistory:
    commits: int = 0
    churn: int = 0
    fix_commits: int = 0
    last_modified: str | None = None
    authors: Counter[str] = field(default_factory=Counter)

    @property
    def distinct_authors(self) -> int:
        return len(self.authors)

    def primary(self) -> tuple[str | None, float]:
        if not self.authors:
            return None, 0.0
        author, count = self.authors.most_common(1)[0]
        return author, count / max(self.commits, 1)


@dataclass
class GitHistory:
    available: bool
    files: dict[str, FileHistory]
    total_commits: int = 0
    capped: bool = False
    note: str | None = None

    @classmethod
    def unavailable(cls, note: str) -> "GitHistory":
        return cls(available=False, files={}, note=note)


def collect_git_history(root: Path, tracked_paths: set[str], commit_cap: int = DEFAULT_COMMIT_CAP) -> GitHistory:
    if not _is_git_repo(root):
        return GitHistory.unavailable("Not a Git repository, so churn and ownership are unavailable.")

    # numstat paths are relative to the repo root; when the scan root is a
    # subdirectory we must strip that prefix to line up with our node paths.
    prefix = _show_prefix(root)
    log = _run_git_log(root, commit_cap)
    if log is None:
        return GitHistory.unavailable("git log failed, so churn and ownership are unavailable.")

    files: dict[str, FileHistory] = defaultdict(FileHistory)
    total_commits = 0

    for record in log.split(RECORD_SEPARATOR):
        record = record.strip("\n")
        if not record:
            continue
        header, _, body = record.partition("\n")
        parts = header.split(UNIT_SEPARATOR)
        if len(parts) != 4:
            continue
        _hash, author, when, subject = parts
        author = author.strip() or "unknown"
        is_fix = bool(FIX_PATTERN.search(subject))
        total_commits += 1

        for line in body.splitlines():
            added, deleted, raw_path = _parse_numstat_line(line)
            if raw_path is None:
                continue
            path = _strip_prefix(_normalize_path(raw_path), prefix)
            if path is None or path not in tracked_paths:
                continue
            stats = files[path]
            stats.commits += 1
            stats.churn += added + deleted
            stats.authors[author] += 1
            if is_fix:
                stats.fix_commits += 1
            # log is newest-first, so the first time we see a file is its latest touch
            if stats.last_modified is None and _is_date(when):
                stats.last_modified = when

    return GitHistory(
        available=True,
        files=dict(files),
        total_commits=total_commits,
        capped=total_commits >= commit_cap,
        note=f"Read the most recent {total_commits} commits." + (" History was capped." if total_commits >= commit_cap else ""),
    )


def recency_days(last_modified: str | None, today: date | None = None) -> int | None:
    if not last_modified:
        return None
    try:
        when = date.fromisoformat(last_modified)
    except ValueError:
        return None
    return ((today or date.today()) - when).days


def _is_git_repo(root: Path) -> bool:
    result = _run_git(root, ["rev-parse", "--is-inside-work-tree"])
    return result is not None and result.strip() == "true"


def _show_prefix(root: Path) -> str:
    result = _run_git(root, ["rev-parse", "--show-prefix"])
    return (result or "").strip()


def _strip_prefix(path: str, prefix: str) -> str | None:
    if not prefix:
        return path
    if path.startswith(prefix):
        return path[len(prefix):]
    return None


def _run_git_log(root: Path, commit_cap: int) -> str | None:
    return _run_git(
        root,
        [
            "log",
            "--no-merges",
            f"-n{commit_cap}",
            "-M",
            "--numstat",
            "--date=short",
            f"--format={RECORD_SEPARATOR}%H{UNIT_SEPARATOR}%an{UNIT_SEPARATOR}%ad{UNIT_SEPARATOR}%s",
            "--",
            ".",
        ],
    )


def _run_git(root: Path, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _parse_numstat_line(line: str) -> tuple[int, int, str | None]:
    parts = line.split("\t")
    if len(parts) != 3:
        return 0, 0, None
    added_raw, deleted_raw, path = parts
    added = 0 if added_raw == "-" else _safe_int(added_raw)
    deleted = 0 if deleted_raw == "-" else _safe_int(deleted_raw)
    return added, deleted, path


def _normalize_path(raw_path: str) -> str:
    # Renames render as "old => new" or "dir/{old => new}/file"; keep the new path.
    if "=>" in raw_path:
        brace = re.sub(r"\{[^}]*=> ?([^}]*)\}", r"\1", raw_path)
        if "=>" in brace:
            brace = brace.split("=>")[-1]
        raw_path = brace.replace("//", "/").strip()
    return raw_path.strip()


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _is_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False
