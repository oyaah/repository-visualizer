from __future__ import annotations

from app.models import EdgeKind
from app.parsers import parse_c_dependencies, parse_javascript_dependencies, parse_python_dependencies


def test_parse_python_imports() -> None:
    deps = parse_python_dependencies("import os\nfrom .utils import helper\nfrom . import sibling\n")
    assert [dep.raw for dep in deps] == ["os", ".utils", ".sibling"]
    assert deps[1].is_relative is True


def test_parse_javascript_imports() -> None:
    deps = parse_javascript_dependencies("import Button from './Button';\nconst x = await import('./lazy')\n")
    assert deps[0].raw == "./Button"
    assert deps[1].kind == EdgeKind.DYNAMIC_IMPORT


def test_parse_c_includes() -> None:
    deps = parse_c_dependencies('#include "local.h"\n#include <stdio.h>\n')
    assert deps[0].raw == "local.h"
    assert deps[0].is_relative is True
    assert deps[1].raw == "stdio.h"
    assert deps[1].is_relative is False
