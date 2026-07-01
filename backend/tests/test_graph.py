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


def test_graph_resolves_extra_languages_and_routes(tmp_path: Path) -> None:
    (tmp_path / "go" / "api").mkdir(parents=True)
    (tmp_path / "go" / "main.go").write_text('package main\nimport "repo/go/api"\nfunc main() {}\n', encoding="utf-8")
    (tmp_path / "go" / "api" / "handler.go").write_text('package api\nfunc Register() { r.GET("/health", h) }\n', encoding="utf-8")
    (tmp_path / "src" / "main" / "java" / "com" / "app").mkdir(parents=True)
    (tmp_path / "src" / "main" / "java" / "com" / "app" / "App.java").write_text('import com.app.Controller;\nclass App { public static void main(String[] args) {} }\n', encoding="utf-8")
    (tmp_path / "src" / "main" / "java" / "com" / "app" / "Controller.java").write_text('@RestController class Controller { @GetMapping("/ping") void ping(){} }\n', encoding="utf-8")
    (tmp_path / "lib").mkdir()
    (tmp_path / "app.rb").write_text("require_relative 'lib/tool'\nget '/home'\n", encoding="utf-8")
    (tmp_path / "lib" / "tool.rb").write_text("class Tool\nend\n", encoding="utf-8")
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "main.rs").write_text("mod worker;\nfn main() {}\n", encoding="utf-8")
    (tmp_path / "src" / "worker.rs").write_text("pub fn run() {}\n", encoding="utf-8")
    (tmp_path / "index.php").write_text("<?php require 'lib.php'; Route::get('/login', 'x');", encoding="utf-8")
    (tmp_path / "lib.php").write_text("<?php class Lib {}", encoding="utf-8")
    (tmp_path / "strings.py").write_text('PATTERN = "@app.get(\\"/fake\\")"\n', encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("go/main.go", "go/api/handler.go") in edges
    assert ("src/main/java/com/app/App.java", "src/main/java/com/app/Controller.java") in edges
    assert ("app.rb", "lib/tool.rb") in edges
    assert ("src/main.rs", "src/worker.rs") in edges
    assert ("index.php", "lib.php") in edges
    routes = {(route.method, route.path, route.framework) for route in graph.routes}
    assert ("GET", "/health", "go-http") in routes
    assert ("GET", "/ping", "spring") in routes
    assert ("GET", "/home", "rails") in routes
    assert ("GET", "/login", "laravel") in routes
    assert ("GET", "/fake", "python") not in routes
    entries = {(entry.kind, entry.file_path) for entry in graph.repo_report.entry_points}
    assert ("go_main", "go/main.go") in entries
    assert ("java_main", "src/main/java/com/app/App.java") in entries
    assert ("rust_main", "src/main.rs") in entries


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


def test_graph_returns_package_summaries_and_risk_scores(tmp_path: Path) -> None:
    (tmp_path / "api").mkdir()
    (tmp_path / "core").mkdir()
    (tmp_path / "api" / "routes.py").write_text("import core.service\nif value:\n    pass\n", encoding="utf-8")
    (tmp_path / "core" / "service.py").write_text("if a:\n    pass\nif b:\n    pass\n", encoding="utf-8")
    (tmp_path / "core" / "model.py").write_text("VALUE = 1\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    risky = next(node for node in graph.nodes if node.path == "core/service.py")
    assert risky.metrics.risk_score > 0
    packages = {summary.name: summary for summary in graph.package_summaries}
    assert packages["core"].files == 2
    assert packages["core"].loc >= 3
    assert "core/service.py" in packages["core"].highest_risk_files
    assert packages["api"].dependency_count == 1


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


def test_graph_resolves_dynamic_import_edges(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.ts").write_text("const lazy = () => import('./lazy');\n", encoding="utf-8")
    (tmp_path / "src" / "lazy.ts").write_text("export const value = 1;\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edges = {(edge.source, edge.target, edge.kind.value) for edge in graph.edges}
    assert ("src/main.ts", "src/lazy.ts", "dynamic_import") in edges
    edge = graph.edges[0]
    assert edge.scope.value == "dynamic"
    assert "dynamic" in edge.label


def test_graph_preserves_type_checking_edge_scope(tmp_path: Path) -> None:
    (tmp_path / "models.py").write_text("class User: pass\n", encoding="utf-8")
    (tmp_path / "service.py").write_text("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import models\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    edge = next(edge for edge in graph.edges if edge.target == "models.py")
    assert edge.scope.value == "type_checking"


def test_graph_attaches_symbol_and_security_hints(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "password = 'abc1234567890SECRET'\n"
        "def risky():\n"
        "    if value:\n"
        "        return eval(value)\n",
        encoding="utf-8",
    )

    graph = build_graph(tmp_path)

    node = graph.nodes[0]
    assert node.symbols[0].name == "risky"
    assert {hint.kind for hint in node.hints} == {"framework", "security"}
    findings = {(finding.kind, finding.file_path) for finding in graph.repo_report.start_here}
    assert ("security", "app.py") in findings


def test_graph_ignores_obvious_secret_placeholders(tmp_path: Path) -> None:
    (tmp_path / "config.py").write_text("api_key = 'your_api_key_here'\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    assert graph.nodes[0].hints == []


def test_graph_security_hint_placeholder_filter_does_not_hide_unsafe_code(tmp_path: Path) -> None:
    (tmp_path / "unsafe.py").write_text("if value < 10:\n    eval(value)\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    assert any(hint.title == "Unsafe API pattern" for hint in graph.nodes[0].hints)
