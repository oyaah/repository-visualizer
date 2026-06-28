from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from app.models import EdgeKind


@dataclass(frozen=True)
class Dependency:
    raw: str
    kind: EdgeKind
    is_relative: bool = False


JS_IMPORT_PATTERNS = [
    re.compile(r"""import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]"""),
    re.compile(r"""export\s+[^'"]+\s+from\s+['"]([^'"]+)['"]"""),
    re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)"""),
]
DYNAMIC_IMPORT_PATTERN = re.compile(r"""import\(\s*['"]([^'"]+)['"]\s*\)""")
INCLUDE_PATTERN = re.compile(r"""^\s*#\s*include\s+([<"])([^>"]+)[>"]""", re.MULTILINE)


def parse_dependencies(relative_path: str, text: str) -> list[Dependency]:
    extension = Path(relative_path).suffix.lower()
    if extension == ".py":
        return parse_python_dependencies(text)
    if extension in {".js", ".jsx", ".ts", ".tsx"}:
        return parse_javascript_dependencies(text)
    if extension in {".c", ".h", ".cc", ".cpp", ".hpp"}:
        return parse_c_dependencies(text)
    return []


def parse_python_dependencies(text: str) -> list[Dependency]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    deps: list[Dependency] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                deps.append(Dependency(raw=alias.name, kind=EdgeKind.IMPORT))
        elif isinstance(node, ast.ImportFrom):
            dots = "." * node.level
            if node.module:
                deps.append(Dependency(raw=f"{dots}{node.module}", kind=EdgeKind.IMPORT, is_relative=node.level > 0))
                if node.level == 0:
                    for alias in node.names:
                        if alias.name != "*":
                            deps.append(Dependency(raw=f"{node.module}.{alias.name}", kind=EdgeKind.IMPORT))
            else:
                for alias in node.names:
                    deps.append(Dependency(raw=f"{dots}{alias.name}", kind=EdgeKind.IMPORT, is_relative=node.level > 0))
    return deps


def parse_javascript_dependencies(text: str) -> list[Dependency]:
    text = strip_javascript_comments(text)
    deps: list[Dependency] = []
    for pattern in JS_IMPORT_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(1)
            deps.append(Dependency(raw=raw, kind=EdgeKind.IMPORT, is_relative=raw.startswith(".")))
    for match in DYNAMIC_IMPORT_PATTERN.finditer(text):
        raw = match.group(1)
        deps.append(Dependency(raw=raw, kind=EdgeKind.DYNAMIC_IMPORT, is_relative=raw.startswith(".")))
    return deps


def strip_javascript_comments(text: str) -> str:
    output: list[str] = []
    index = 0
    quote: str | None = None
    escaping = False
    while index < len(text):
        current = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if quote:
            output.append(current)
            if escaping:
                escaping = False
            elif current == "\\":
                escaping = True
            elif current == quote:
                quote = None
            index += 1
            continue

        if current in {"'", '"', "`"}:
            quote = current
            output.append(current)
            index += 1
            continue

        if current == "/" and next_char == "/":
            while index < len(text) and text[index] != "\n":
                index += 1
            output.append("\n")
            continue

        if current == "/" and next_char == "*":
            index += 2
            while index + 1 < len(text) and not (text[index] == "*" and text[index + 1] == "/"):
                output.append("\n" if text[index] == "\n" else " ")
                index += 1
            index += 2
            continue

        output.append(current)
        index += 1

    return "".join(output)


def parse_c_dependencies(text: str) -> list[Dependency]:
    deps: list[Dependency] = []
    for match in INCLUDE_PATTERN.finditer(text):
        delimiter, raw = match.groups()
        deps.append(Dependency(raw=raw, kind=EdgeKind.INCLUDE, is_relative=delimiter == '"'))
    return deps
