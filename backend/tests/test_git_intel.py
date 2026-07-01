from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.git_history import GitHistory, collect_git_history
from app.graph import (
    build_package_edges,
    build_package_summaries,
    dead_code_findings,
    is_test_path,
)
from app.graph import build_graph
from app.models import FileMetrics, GraphNode


def _git(repo: Path, *args: str, author: str | None = None) -> None:
    env = None
    if author:
        env = {
            "GIT_AUTHOR_NAME": author,
            "GIT_AUTHOR_EMAIL": f"{author}@example.com",
            "GIT_COMMITTER_NAME": author,
            "GIT_COMMITTER_EMAIL": f"{author}@example.com",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(repo),
        }
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def _has_git() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _make_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "commit.gpgsign", "false")


def _node(path: str, *, loc: int = 10, complexity: int = 1, dependents: int = 0) -> GraphNode:
    folder = path.rsplit("/", 1)[0] if "/" in path else ""
    return GraphNode(
        id=path,
        path=path,
        label=path.rsplit("/", 1)[-1],
        folder=folder,
        extension="." + path.rsplit(".", 1)[-1],
        metrics=FileMetrics(loc=loc, total_lines=loc, size_bytes=loc * 10, complexity=complexity, dependent_count=dependents),
    )


pytestmark = pytest.mark.skipif(not _has_git(), reason="git binary not available")


def test_collect_git_history_tracks_churn_and_ownership(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    (tmp_path / "app").mkdir()
    target = tmp_path / "app" / "core.py"
    target.write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "add core", author="alice")
    target.write_text("x = 1\ny = 2\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fix core crash", author="bob")

    history = collect_git_history(tmp_path, {"app/core.py"})

    record = history.files["app/core.py"]
    assert history.available is True
    assert record.commits == 2
    assert record.fix_commits == 1
    assert record.distinct_authors == 2


def test_collect_git_history_handles_subdirectory_scan_root(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "main.py").write_text("print('hi')\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init backend")

    history = collect_git_history(backend, {"main.py"})

    assert history.available is True
    assert history.files["main.py"].commits == 1


def test_build_graph_attaches_git_and_raises_risk(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fix initial bug")

    graph = build_graph(tmp_path)

    assert graph.git.available is True
    assert any(node.git and node.git.commits >= 1 for node in graph.nodes)
    assert any(summary.primary_author for summary in graph.package_summaries)


def test_git_unavailable_outside_repo(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("VALUE = 1\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    assert graph.git.available is False
    assert all(node.git is None for node in graph.nodes)


def test_build_package_edges_counts_cross_package_imports() -> None:
    nodes = [_node("app/main.py"), _node("app/util.py"), _node("tests/test_main.py")]
    nodes[2].imports = ["app/main.py"]
    nodes[0].imports = ["app/util.py"]

    edges = build_package_edges(nodes)

    assert any(edge.source == "tests" and edge.target == "app" and edge.count == 1 for edge in edges)
    assert all(edge.source != edge.target for edge in edges)


def test_build_package_summaries_without_git_has_no_owner() -> None:
    nodes = [_node("app/main.py", loc=50)]
    summaries = build_package_summaries(nodes, GitHistory.unavailable("n/a"))
    assert summaries[0].primary_author is None
    assert summaries[0].bus_factor is None


def test_dead_code_findings_flags_unimported_file() -> None:
    used = _node("app/used.py", loc=50, dependents=2)
    orphan = _node("app/orphan.py", loc=80, dependents=0)
    test_file = _node("tests/test_used.py", loc=80, dependents=0)

    findings = dead_code_findings([used, orphan, test_file], entry_paths=set())

    paths = {finding.file_path for finding in findings}
    assert "app/orphan.py" in paths
    assert "tests/test_used.py" not in paths
    assert "app/used.py" not in paths


def test_is_test_path() -> None:
    assert is_test_path("tests/test_x.py")
    assert is_test_path("src/foo.test.tsx")
    assert not is_test_path("src/foo.py")
