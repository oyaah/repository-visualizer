from __future__ import annotations

from dataclasses import dataclass
import json
import posixpath
from pathlib import Path

from app.models import AnalyzeRequest, EdgeKind, FileMetrics, GraphEdge, GraphNode, GraphResponse, GraphStats
from app.parsers import Dependency, parse_dependencies
from app.scanner import ScannedFile, scan_repository

RESOLUTION_EXTENSIONS = ["", ".py", ".js", ".jsx", ".ts", ".tsx", ".c", ".h", ".cc", ".cpp", ".hpp", "/index.js", "/index.ts", "/__init__.py"]


@dataclass(frozen=True)
class TsPathAlias:
    pattern: str
    targets: list[str]
    base_path: str


def build_graph(root: Path, options: AnalyzeRequest | None = None) -> GraphResponse:
    scan_result = scan_repository(root, options)
    scanned_files = scan_result.files
    by_path = {item.relative_path: item for item in scanned_files}
    ts_aliases = load_ts_path_aliases(root)
    nodes = {
        item.relative_path: GraphNode(
            id=item.relative_path,
            path=item.relative_path,
            label=Path(item.relative_path).name,
            folder=item.folder,
            extension=item.extension,
            metrics=item.metrics.model_copy(),
        )
        for item in scanned_files
    }
    edges: list[GraphEdge] = []
    edge_ids: set[str] = set()

    for item in scanned_files:
        for dep in parse_dependencies(item.relative_path, item.text):
            target = resolve_dependency(item, dep, by_path, ts_aliases)
            if target:
                edge_id = f"{item.relative_path}->{target}:{dep.kind.value}"
                if edge_id in edge_ids:
                    continue
                edge_ids.add(edge_id)
                edge = GraphEdge(
                    id=edge_id,
                    source=item.relative_path,
                    target=target,
                    kind=dep.kind,
                    label=dep.kind.value.replace("_", " "),
                )
                edges.append(edge)
                nodes[item.relative_path].imports.append(target)
                nodes[target].imported_by.append(item.relative_path)
            elif dep.is_relative:
                nodes[item.relative_path].unresolved_imports.append(dep.raw)
            else:
                nodes[item.relative_path].external_imports.append(dep.raw)

    for node in nodes.values():
        node.imports = sorted(set(node.imports))
        node.imported_by = sorted(set(node.imported_by))
        node.unresolved_imports = sorted(set(node.unresolved_imports))
        node.external_imports = sorted(set(node.external_imports))
        node.metrics = FileMetrics(
            **node.metrics.model_dump(exclude={"dependency_count", "dependent_count"}),
            dependency_count=len(node.imports),
            dependent_count=len(node.imported_by),
        )

    return GraphResponse(
        root_path=str(root.resolve()),
        nodes=sorted(nodes.values(), key=lambda node: node.path),
        edges=sorted(edges, key=lambda edge: edge.id),
        ignored_directories=scan_result.ignored_directories,
        stats=GraphStats(
            total_files_found=scan_result.total_files_found,
            analyzed_files=len(scanned_files),
            skipped_files=scan_result.skipped_files,
            skipped_reasons=scan_result.skipped_reasons,
            truncated=scan_result.truncated,
            warnings=scan_result.warnings,
        ),
    )


def resolve_dependency(source: ScannedFile, dependency: Dependency, files: dict[str, ScannedFile], ts_aliases: list[TsPathAlias] | None = None) -> str | None:
    if source.extension == ".py":
        return resolve_python_dependency(source, dependency, files)
    if source.extension in {".js", ".jsx", ".ts", ".tsx"}:
        if dependency.is_relative:
            return resolve_path_like_dependency(source, dependency.raw, files)
        return resolve_ts_alias_dependency(dependency.raw, files, ts_aliases or [])
    if source.extension in {".c", ".h", ".cc", ".cpp", ".hpp"} and dependency.is_relative:
        return resolve_path_like_dependency(source, dependency.raw, files)
    return None


def resolve_python_dependency(source: ScannedFile, dependency: Dependency, files: dict[str, ScannedFile]) -> str | None:
    if dependency.is_relative:
        level = len(dependency.raw) - len(dependency.raw.lstrip("."))
        module = dependency.raw.lstrip(".")
        base = Path(source.relative_path).parent
        for _ in range(max(level - 1, 0)):
            base = base.parent
        candidate = base / module.replace(".", "/")
        return first_existing_candidate(candidate.as_posix(), files, python=True)

    package_path = dependency.raw.replace(".", "/")
    return first_existing_candidate(package_path, files, python=True) or first_existing_candidate(f"src/{package_path}", files, python=True)


def resolve_path_like_dependency(source: ScannedFile, raw: str, files: dict[str, ScannedFile]) -> str | None:
    base = Path(source.relative_path).parent
    candidate = posixpath.normpath((base / raw).as_posix())
    return first_existing_candidate(candidate, files)


def first_existing_candidate(candidate: str, files: dict[str, ScannedFile], python: bool = False) -> str | None:
    candidate = posixpath.normpath(candidate.strip("/"))
    candidates = [candidate + ext for ext in RESOLUTION_EXTENSIONS]
    if python:
        candidates.extend([f"{candidate}/__init__.py"])
    normalized = [Path(item).as_posix().replace("./", "") for item in candidates]
    for path in normalized:
        if path in files:
            return path
    return None


def load_ts_path_aliases(root: Path) -> list[TsPathAlias]:
    aliases: list[TsPathAlias] = []
    for tsconfig in sorted(root.rglob("tsconfig.json")):
        if any(part in {".git", "node_modules", "dist", "build"} for part in tsconfig.relative_to(root).parts):
            continue
        aliases.extend(load_tsconfig_aliases(root, tsconfig))
    return aliases


def load_tsconfig_aliases(root: Path, tsconfig: Path) -> list[TsPathAlias]:
    try:
        config = json.loads(tsconfig.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    compiler_options = config.get("compilerOptions", {})
    if not isinstance(compiler_options, dict):
        return []
    base_url = compiler_options.get("baseUrl", ".")
    paths = compiler_options.get("paths", {})
    if not isinstance(paths, dict):
        return []

    aliases: list[TsPathAlias] = []
    config_dir = tsconfig.parent.relative_to(root).as_posix()
    config_prefix = "" if config_dir == "." else config_dir
    base_path = posixpath.normpath(posixpath.join(config_prefix, str(base_url)))
    for pattern, targets in paths.items():
        if isinstance(pattern, str) and isinstance(targets, list):
            normalized_targets = [target for target in targets if isinstance(target, str)]
            if normalized_targets:
                aliases.append(TsPathAlias(pattern=pattern, targets=normalized_targets, base_path=base_path))
    return aliases


def resolve_ts_alias_dependency(raw: str, files: dict[str, ScannedFile], aliases: list[TsPathAlias]) -> str | None:
    for alias in aliases:
        wildcard = alias_wildcard(raw, alias.pattern)
        if wildcard is None:
            continue
        for target_pattern in alias.targets:
            target = target_pattern.replace("*", wildcard)
            candidate = posixpath.normpath(posixpath.join(alias.base_path, target))
            resolved = first_existing_candidate(candidate, files)
            if resolved:
                return resolved
    return None


def alias_wildcard(raw: str, pattern: str) -> str | None:
    if "*" not in pattern:
        return "" if raw == pattern else None
    prefix, suffix = pattern.split("*", 1)
    if not raw.startswith(prefix) or not raw.endswith(suffix):
        return None
    return raw[len(prefix) : len(raw) - len(suffix) if suffix else len(raw)]
