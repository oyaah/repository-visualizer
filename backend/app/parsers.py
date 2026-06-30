from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from app.models import EdgeKind, EdgeScope


@dataclass(frozen=True)
class Dependency:
    raw: str
    kind: EdgeKind
    is_relative: bool = False
    scope: EdgeScope = EdgeScope.TOP_LEVEL


JS_IMPORT_PATTERNS = [
    re.compile(r"""import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]"""),
    re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)"""),
]
JS_RE_EXPORT_PATTERN = re.compile(r"""export\s+[^'"]+\s+from\s+['"]([^'"]+)['"]""")
DYNAMIC_IMPORT_PATTERN = re.compile(r"""import\(\s*['"]([^'"]+)['"]\s*\)""")
INCLUDE_PATTERN = re.compile(r"""^\s*#\s*include\s+([<"])([^>"]+)[>"]""", re.MULTILINE)
_DEPENDENCY_CACHE: dict[tuple[str, str], list[Dependency]] = {}
_CACHE_LIMIT = 2048


def parse_dependencies(relative_path: str, text: str) -> list[Dependency]:
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    key = (relative_path, digest)
    if key in _DEPENDENCY_CACHE:
        return list(_DEPENDENCY_CACHE[key])

    extension = Path(relative_path).suffix.lower()
    if extension == ".py":
        deps = parse_python_dependencies(text)
    elif extension in {".js", ".jsx", ".ts", ".tsx"}:
        deps = parse_javascript_dependencies(text)
    elif extension in {".c", ".h", ".cc", ".cpp", ".hpp"}:
        deps = parse_c_dependencies(text)
    else:
        deps = []

    if len(_DEPENDENCY_CACHE) >= _CACHE_LIMIT:
        _DEPENDENCY_CACHE.clear()
    _DEPENDENCY_CACHE[key] = deps
    return list(deps)


def clear_dependency_cache() -> None:
    _DEPENDENCY_CACHE.clear()


def parse_python_dependencies(text: str) -> list[Dependency]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    deps: list[Dependency] = []
    type_checking_depth = 0
    conditional_depth = 0
    lazy_depth = 0

    def scope() -> EdgeScope:
        if type_checking_depth:
            return EdgeScope.TYPE_CHECKING
        if lazy_depth:
            return EdgeScope.LAZY
        if conditional_depth:
            return EdgeScope.CONDITIONAL
        return EdgeScope.TOP_LEVEL

    def visit(node: ast.AST) -> None:
        nonlocal conditional_depth, lazy_depth, type_checking_depth
        if isinstance(node, ast.Import):
            for alias in node.names:
                deps.append(Dependency(raw=alias.name, kind=EdgeKind.IMPORT, scope=scope()))
            return
        elif isinstance(node, ast.ImportFrom):
            dots = "." * node.level
            if node.module:
                deps.append(Dependency(raw=f"{dots}{node.module}", kind=EdgeKind.IMPORT, is_relative=node.level > 0, scope=scope()))
                if node.level == 0:
                    for alias in node.names:
                        if alias.name != "*":
                            deps.append(Dependency(raw=f"{node.module}.{alias.name}", kind=EdgeKind.IMPORT, scope=scope()))
            else:
                for alias in node.names:
                    deps.append(Dependency(raw=f"{dots}{alias.name}", kind=EdgeKind.IMPORT, is_relative=node.level > 0, scope=scope()))
            return

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            lazy_depth += 1
            for child in ast.iter_child_nodes(node):
                visit(child)
            lazy_depth -= 1
            return

        if isinstance(node, ast.If):
            if is_type_checking_guard(node.test):
                type_checking_depth += 1
                for child in node.body:
                    visit(child)
                type_checking_depth -= 1
                for child in node.orelse:
                    visit(child)
                return
            conditional_depth += 1
            for child in node.body + node.orelse:
                visit(child)
            conditional_depth -= 1
            return

        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return deps


def is_type_checking_guard(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    if isinstance(node, ast.Attribute):
        return node.attr == "TYPE_CHECKING"
    return False


def parse_javascript_dependencies(text: str) -> list[Dependency]:
    text = strip_javascript_comments(text)
    deps: list[Dependency] = []
    for match in JS_RE_EXPORT_PATTERN.finditer(text):
        raw = match.group(1)
        deps.append(Dependency(raw=raw, kind=EdgeKind.IMPORT, is_relative=raw.startswith("."), scope=EdgeScope.RE_EXPORT))
    for pattern in JS_IMPORT_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(1)
            deps.append(Dependency(raw=raw, kind=EdgeKind.IMPORT, is_relative=raw.startswith("."), scope=javascript_scope(text, match.start())))
    for match in DYNAMIC_IMPORT_PATTERN.finditer(text):
        raw = match.group(1)
        deps.append(Dependency(raw=raw, kind=EdgeKind.DYNAMIC_IMPORT, is_relative=raw.startswith("."), scope=EdgeScope.DYNAMIC))
    return deps


def javascript_scope(text: str, start: int) -> EdgeScope:
    line_start = text.rfind("\n", 0, start) + 1
    prefix = text[line_start:start].strip()
    if prefix.startswith(("if", "for", "while", "switch", "try", "catch")):
        return EdgeScope.CONDITIONAL
    if prefix or "function " in text[max(0, start - 120) : start] or "=>" in text[max(0, start - 120) : start]:
        return EdgeScope.LAZY
    return EdgeScope.TOP_LEVEL


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
