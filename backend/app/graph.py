from __future__ import annotations

from pathlib import Path

from app.models import AnalyzeRequest, EdgeKind, FileMetrics, GraphEdge, GraphNode, GraphResponse, GraphStats
from app.parsers import Dependency, parse_dependencies
from app.scanner import ScannedFile, scan_repository

RESOLUTION_EXTENSIONS = ["", ".py", ".js", ".jsx", ".ts", ".tsx", ".c", ".h", ".cc", ".cpp", ".hpp", "/index.js", "/index.ts", "/__init__.py"]


def build_graph(root: Path, options: AnalyzeRequest | None = None) -> GraphResponse:
    scan_result = scan_repository(root, options)
    scanned_files = scan_result.files
    by_path = {item.relative_path: item for item in scanned_files}
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
            target = resolve_dependency(item, dep, by_path)
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
            truncated=scan_result.truncated,
            warnings=scan_result.warnings,
        ),
    )


def resolve_dependency(source: ScannedFile, dependency: Dependency, files: dict[str, ScannedFile]) -> str | None:
    if source.extension == ".py":
        return resolve_python_dependency(source, dependency, files)
    if source.extension in {".js", ".jsx", ".ts", ".tsx"}:
        return resolve_path_like_dependency(source, dependency.raw, files)
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
    return first_existing_candidate(package_path, files, python=True)


def resolve_path_like_dependency(source: ScannedFile, raw: str, files: dict[str, ScannedFile]) -> str | None:
    base = Path(source.relative_path).parent
    candidate = (base / raw).as_posix()
    return first_existing_candidate(candidate, files)


def first_existing_candidate(candidate: str, files: dict[str, ScannedFile], python: bool = False) -> str | None:
    candidate = candidate.strip("/")
    candidates = [candidate + ext for ext in RESOLUTION_EXTENSIONS]
    if python:
        candidates.extend([f"{candidate}/__init__.py"])
    normalized = [Path(item).as_posix().replace("./", "") for item in candidates]
    for path in normalized:
        if path in files:
            return path
    return None
