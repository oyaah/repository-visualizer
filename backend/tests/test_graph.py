from __future__ import annotations

from pathlib import Path

from app.graph import build_graph
from app.models import AnalyzeRequest


def test_graph_resolves_javascript_and_c_dependencies(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.tsx").write_text("import Button from './Button';\n", encoding="utf-8")
    (tmp_path / "src" / "Button.tsx").write_text("export function Button() { return null }\n", encoding="utf-8")
    (tmp_path / "native").mkdir()
    (tmp_path / "native" / "main.c").write_text('#include "local.h"\n#include <stdio.h>\n', encoding="utf-8")
    (tmp_path / "native" / "local.h").write_text("void run(void);\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target, edge.kind.value) for edge in graph.edges}
    assert ("src/App.tsx", "src/Button.tsx", "import") in edges
    assert ("native/main.c", "native/local.h", "include") in edges
    main_node = next(node for node in graph.nodes if node.path == "native/main.c")
    assert "stdio.h" in main_node.external_imports


def test_graph_resolves_python_src_layout_imports(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "main.py").write_text("import pkg.utils\n", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "utils.py").write_text("VALUE = 1\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("src/pkg/main.py", "src/pkg/utils.py") in edges


def test_graph_resolves_typescript_path_aliases(tmp_path: Path) -> None:
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}', encoding="utf-8")
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "src" / "App.tsx").write_text("import Panel from '@/components/Panel';\n", encoding="utf-8")
    (tmp_path / "src" / "components" / "Panel.tsx").write_text("export default function Panel() { return null }\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("src/App.tsx", "src/components/Panel.tsx") in edges


def test_graph_resolves_nested_typescript_path_aliases(tmp_path: Path) -> None:
    (tmp_path / "frontend" / "src" / "components").mkdir(parents=True)
    (tmp_path / "frontend" / "tsconfig.json").write_text('{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}', encoding="utf-8")
    (tmp_path / "frontend" / "src" / "App.tsx").write_text("import Panel from '@/components/Panel';\n", encoding="utf-8")
    (tmp_path / "frontend" / "src" / "components" / "Panel.tsx").write_text("export default function Panel() { return null }\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("frontend/src/App.tsx", "frontend/src/components/Panel.tsx") in edges


def test_graph_resolves_parent_directory_imports(tmp_path: Path) -> None:
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "src" / "utils.ts").write_text("export const value = 1;\n", encoding="utf-8")
    (tmp_path / "src" / "components" / "Panel.tsx").write_text("import { value } from '../utils';\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("src/components/Panel.tsx", "src/utils.ts") in edges


def test_graph_resolves_from_import_module_aliases(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "main.py").write_text("from pkg import utils\n", encoding="utf-8")
    (tmp_path / "pkg" / "utils.py").write_text("VALUE = 1\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("pkg/main.py", "pkg/utils.py") in edges


def test_graph_handles_cycles_without_recursing(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import a\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("a.py", "b.py") in edges
    assert ("b.py", "a.py") in edges
    assert len(graph.edges) == 2


def test_graph_deduplicates_repeated_import_edges(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import b\nimport b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("VALUE = 1\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    assert [(edge.source, edge.target) for edge in graph.edges] == [("a.py", "b.py")]
    node = next(node for node in graph.nodes if node.path == "a.py")
    assert node.metrics.dependency_count == 1


def test_graph_includes_scan_metadata(tmp_path: Path) -> None:
    for index in range(3):
        (tmp_path / f"module_{index}.py").write_text("print('ok')\n", encoding="utf-8")

    graph = build_graph(tmp_path, AnalyzeRequest(root_path=str(tmp_path), max_files=2))

    assert len(graph.nodes) == 2
    assert graph.stats.total_files_found == 3
    assert graph.stats.analyzed_files == 2
    assert graph.stats.skipped_files == 1
    assert graph.stats.truncated is True
    assert graph.stats.warnings
