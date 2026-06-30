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


def test_graph_resolves_relative_package_symbol_imports_to_init(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("class Flask: pass\n", encoding="utf-8")
    (tmp_path / "pkg" / "cli.py").write_text("from . import Flask\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("pkg/cli.py", "pkg/__init__.py") in edges


def test_graph_handles_cycles_without_recursing(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import a\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("a.py", "b.py") in edges
    assert ("b.py", "a.py") in edges
    assert len(graph.edges) == 2
    assert graph.cycles[0].files == ["a.py", "b.py"]
    assert graph.cycles[0].edge_count == 2


def test_graph_returns_no_cycles_for_acyclic_graph(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("VALUE = 1\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    assert graph.cycles == []


def test_graph_returns_folder_summaries(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("import src.utils\nif True:\n    pass\n", encoding="utf-8")
    (tmp_path / "src" / "utils.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "root.py").write_text("print('ok')\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    summaries = {summary.name: summary for summary in graph.folder_summaries}
    assert summaries["src"].files == 2
    assert summaries["src"].loc == 4
    assert summaries["root"].files == 1


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


def test_graph_returns_actionable_repo_report(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import b\nfrom .missing import thing\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import a\n", encoding="utf-8")
    (tmp_path / "shared.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "one.py").write_text("import shared\n", encoding="utf-8")
    (tmp_path / "two.py").write_text("import shared\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    findings = {(finding.kind, finding.file_path) for finding in graph.repo_report.start_here}
    assert ("cycle", "a.py") in findings
    assert ("unresolved_import", "a.py") in findings
    assert ("hub", "shared.py") in findings
    assert graph.repo_report.reading_order[0] in {"a.py", "shared.py"}


def test_graph_marks_package_init_hubs_as_api_facades(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    for name in ("one.py", "two.py", "three.py"):
        (tmp_path / name).write_text("import pkg\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    facade = next(finding for finding in graph.repo_report.start_here if finding.file_path == "pkg/__init__.py")
    assert facade.kind == "api_facade"
    assert facade.confidence == "medium"
    assert "public surface" in facade.detail


def test_graph_detects_likely_entry_points(tmp_path: Path) -> None:
    (tmp_path / "api.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    (tmp_path / "cli.py").write_text('if __name__ == "__main__":\n    print("ok")\n', encoding="utf-8")
    (tmp_path / "App.tsx").write_text("import { createRoot } from 'react-dom/client';\ncreateRoot(root).render(null);\n", encoding="utf-8")
    (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (tmp_path / "util.py").write_text("VALUE = 1\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    entries = {(entry.kind, entry.file_path) for entry in graph.repo_report.entry_points}
    assert ("python_web", "api.py") in entries
    assert ("python_cli", "cli.py") in entries
    assert ("react_root", "App.tsx") in entries
    assert ("native_main", "main.c") in entries
    assert all(entry.file_path != "util.py" for entry in graph.repo_report.entry_points)


def test_graph_labels_generic_python_route_decorators_without_fastapi_claim(tmp_path: Path) -> None:
    (tmp_path / "views.py").write_text("@bp.get('/items')\ndef items():\n    return ''\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    entry = graph.repo_report.entry_points[0]
    assert entry.file_path == "views.py"
    assert entry.label == "Likely Python web routes"


def test_graph_detects_metadata_entry_points(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"start":"node src/server.js"},"bin":{"tool":"bin/cli.js"}}', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "bin").mkdir()
    (tmp_path / "src" / "server.js").write_text("console.log('server')\n", encoding="utf-8")
    (tmp_path / "bin" / "cli.js").write_text("console.log('cli')\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project.scripts]\nrv = "pkg.main:run"\n', encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "main.py").write_text("def run():\n    pass\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    entries = {(entry.kind, entry.file_path, entry.label) for entry in graph.repo_report.entry_points}
    assert ("package_script", "src/server.js", "Package script: start") in entries
    assert ("package_bin", "bin/cli.js", "Package bin: tool") in entries
    assert ("python_script", "pkg/main.py", "Python script: rv") in entries


def test_graph_flags_orphan_files(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text('import helper\nif __name__ == "__main__":\n    helper.run()\n', encoding="utf-8")
    (tmp_path / "helper.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "orphan.py").write_text("VALUE = 2\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    orphans = {finding.file_path for finding in graph.repo_report.orphans}
    assert "orphan.py" in orphans
    assert "helper.py" not in orphans  # imported by main.py
    assert "main.py" not in orphans  # detected entry point


def test_graph_orphans_exclude_tests_and_package_init(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "test_thing.py").write_text("VALUE = 1\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    orphans = {finding.file_path for finding in graph.repo_report.orphans}
    assert "pkg/__init__.py" not in orphans
    assert "test_thing.py" not in orphans


def test_graph_resolves_dynamic_import_edges(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.ts").write_text("const lazy = () => import('./lazy');\n", encoding="utf-8")
    (tmp_path / "src" / "lazy.ts").write_text("export const value = 1;\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target, edge.kind.value) for edge in graph.edges}
    assert ("src/main.ts", "src/lazy.ts", "dynamic_import") in edges
