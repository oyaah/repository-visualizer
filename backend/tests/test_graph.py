from __future__ import annotations

from pathlib import Path

from app.graph import build_graph


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


def test_graph_handles_cycles_without_recursing(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import a\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("a.py", "b.py") in edges
    assert ("b.py", "a.py") in edges
    assert len(graph.edges) == 2

