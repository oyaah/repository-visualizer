from __future__ import annotations

from pathlib import Path

from app.graph import build_graph


def _edges(graph) -> set[tuple[str, str]]:
    return {(edge.source, edge.target) for edge in graph.edges}


def test_java_package_imports_resolve(tmp_path: Path) -> None:
    (tmp_path / "com" / "app").mkdir(parents=True)
    (tmp_path / "com" / "app" / "Main.java").write_text(
        "package com.app;\nimport com.app.Service;\npublic class Main { public static void main(String[] a){} }\n",
        encoding="utf-8",
    )
    (tmp_path / "com" / "app" / "Service.java").write_text("package com.app;\npublic class Service {}\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    assert ("com/app/Main.java", "com/app/Service.java") in _edges(graph)
    assert any(entry.kind == "java_main" for entry in graph.repo_report.entry_points)


def test_go_module_imports_resolve(tmp_path: Path) -> None:
    (tmp_path / "db").mkdir()
    (tmp_path / "main.go").write_text('package main\nimport (\n  "myapp/db"\n  "fmt"\n)\nfunc main(){ fmt.Println(db.X) }\n', encoding="utf-8")
    (tmp_path / "db" / "store.go").write_text("package db\nvar X = 1\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    assert ("main.go", "db/store.go") in _edges(graph)
    main_node = next(node for node in graph.nodes if node.path == "main.go")
    assert "fmt" in main_node.external_imports


def test_ruby_require_relative_resolves(tmp_path: Path) -> None:
    (tmp_path / "app.rb").write_text("require_relative 'helper'\nputs 1\n", encoding="utf-8")
    (tmp_path / "helper.rb").write_text("def help; end\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    assert ("app.rb", "helper.rb") in _edges(graph)


def test_rust_mod_and_use_resolve(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text("mod util;\nfn main(){ util::run(); }\n", encoding="utf-8")
    (tmp_path / "src" / "util.rs").write_text("pub fn run(){}\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    assert ("src/main.rs", "src/util.rs") in _edges(graph)
    assert any(entry.kind == "rust_main" for entry in graph.repo_report.entry_points)


def test_php_require_resolves(tmp_path: Path) -> None:
    (tmp_path / "index.php").write_text("<?php require_once 'lib.php'; ?>", encoding="utf-8")
    (tmp_path / "lib.php").write_text("<?php function f(){} ?>", encoding="utf-8")

    graph = build_graph(tmp_path)

    assert ("index.php", "lib.php") in _edges(graph)


def test_extract_routes_across_frameworks(tmp_path: Path) -> None:
    (tmp_path / "api.py").write_text(
        'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/users")\ndef u(): ...\n@app.post("/users")\ndef c(): ...\n',
        encoding="utf-8",
    )
    (tmp_path / "routes.js").write_text('router.get("/health", h)\napp.post("/login", l)\n', encoding="utf-8")
    (tmp_path / "Ctrl.java").write_text('@RestController class Ctrl { @GetMapping("/ping") void p(){} }\n', encoding="utf-8")

    graph = build_graph(tmp_path)

    routes = {(route.method, route.path, route.framework) for route in graph.routes}
    assert ("GET", "/users", "python") in routes
    assert ("POST", "/users", "python") in routes
    assert ("GET", "/health", "express") in routes
    assert ("GET", "/ping", "spring") in routes


def test_scan_only_languages_appear_with_metrics(tmp_path: Path) -> None:
    (tmp_path / "App.kt").write_text("import kotlin.io\nclass App { fun run() {} }\n", encoding="utf-8")
    (tmp_path / "View.swift").write_text("import SwiftUI\nstruct View {}\n", encoding="utf-8")
    (tmp_path / "Program.cs").write_text("using System;\nclass Program {}\n", encoding="utf-8")

    graph = build_graph(tmp_path)

    paths = {node.path for node in graph.nodes}
    assert {"App.kt", "View.swift", "Program.cs"} <= paths
    kotlin = next(node for node in graph.nodes if node.path == "App.kt")
    assert "kotlin.io" in kotlin.external_imports
