from __future__ import annotations

from app.models import EdgeKind
import pytest

from app.parsers import clear_dependency_cache, parse_c_dependencies, parse_dependencies, parse_javascript_dependencies, parse_python_dependencies, parse_symbols


def test_parse_python_imports() -> None:
    deps = parse_python_dependencies("import os\nfrom .utils import helper\nfrom . import sibling\n")
    assert [dep.raw for dep in deps] == ["os", ".utils", ".sibling"]
    assert deps[1].is_relative is True


def test_parse_javascript_imports() -> None:
    deps = parse_javascript_dependencies("import Button from './Button';\nconst x = await import('./lazy')\n")
    assert deps[0].raw == "./Button"
    assert deps[1].kind == EdgeKind.DYNAMIC_IMPORT
    assert deps[1].scope.value == "dynamic"


def test_parse_python_import_scopes() -> None:
    deps = parse_python_dependencies(
        "from typing import TYPE_CHECKING\n"
        "import top\n"
        "if TYPE_CHECKING:\n"
        "    import typed\n"
        "if enabled:\n"
        "    import conditional\n"
        "def run():\n"
        "    import lazy\n"
    )

    scopes = {dep.raw: dep.scope.value for dep in deps}
    assert scopes["top"] == "top_level"
    assert scopes["typed"] == "type_checking"
    assert scopes["conditional"] == "conditional"
    assert scopes["lazy"] == "lazy"


def test_parse_javascript_reexport_and_conditional_scopes() -> None:
    deps = parse_javascript_dependencies("export { value } from './value';\nif (ok) require('./conditional');\n")

    scopes = {dep.raw: dep.scope.value for dep in deps}
    assert scopes["./value"] == "re_export"
    assert scopes["./conditional"] == "conditional"


def test_parse_javascript_ignores_commented_imports() -> None:
    deps = parse_javascript_dependencies("// import Hidden from './Hidden';\n/* require('./unused') */\nimport Visible from './Visible';\n")
    assert [dep.raw for dep in deps] == ["./Visible"]


def test_parse_c_includes() -> None:
    deps = parse_c_dependencies('#include "local.h"\n#include <stdio.h>\n')
    assert deps[0].raw == "local.h"
    assert deps[0].is_relative is True
    assert deps[1].raw == "stdio.h"
    assert deps[1].is_relative is False


def test_parse_dependencies_caches_by_content_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_dependency_cache()
    first = parse_dependencies("app.py", "import os\n")

    def fail_parse(_: str):
        raise AssertionError("cache missed")

    monkeypatch.setattr("app.parsers.parse_python_dependencies", fail_parse)

    assert parse_dependencies("app.py", "import os\n") == first


def test_parse_python_symbols_orders_hotspots() -> None:
    symbols = parse_symbols("app.py", "def simple():\n    pass\n\ndef complex():\n    if a:\n        pass\n    for item in items:\n        pass\n")

    assert [(symbol.name, symbol.kind) for symbol in symbols[:2]] == [("complex", "function"), ("simple", "function")]
    assert symbols[0].complexity > symbols[1].complexity
    assert symbols[0].line == 4


def test_parse_javascript_symbols() -> None:
    symbols = parse_symbols("app.tsx", "export function App() { return null }\nconst load = () => import('./x')\nclass Panel {}\n")

    names = {symbol.name for symbol in symbols}
    assert {"App", "load", "Panel"} <= names
