from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import posixpath
import re
import tomllib
from pathlib import Path

from app.models import (
    AnalyzeRequest,
    CycleSummary,
    EdgeKind,
    EntryPointSummary,
    FileMetrics,
    FolderSummary,
    GraphEdge,
    GraphNode,
    GraphResponse,
    GraphStats,
    RepoReport,
    ReportFinding,
)
from app.parsers import Dependency, parse_dependencies
from app.scanner import ScannedFile, is_test_like, scan_repository

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

    sorted_nodes = sorted(nodes.values(), key=lambda node: node.path)
    sorted_edges = sorted(edges, key=lambda edge: edge.id)
    folder_summaries = build_folder_summaries(sorted_nodes)
    cycles = find_cycles(sorted_nodes, sorted_edges)

    return GraphResponse(
        root_path=str(root.resolve()),
        nodes=sorted_nodes,
        edges=sorted_edges,
        folder_summaries=folder_summaries,
        cycles=cycles,
        repo_report=build_repo_report(root, sorted_nodes, cycles, scanned_files),
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


def build_repo_report(root: Path, nodes: list[GraphNode], cycles: list[CycleSummary], scanned_files: list[ScannedFile]) -> RepoReport:
    findings: list[ReportFinding] = []

    for cycle in cycles[:2]:
        package_cycle = any(is_package_init(path) for path in cycle.files)
        findings.append(
            ReportFinding(
                kind="cycle",
                title="Dependency cycle",
                file_path=cycle.files[0],
                detail=cycle_detail(cycle.files),
                severity="medium" if package_cycle else "high",
                confidence="medium" if package_cycle else "high",
                related_files=cycle.files,
            )
        )

    unresolved = sorted(
        (node for node in nodes if node.unresolved_imports),
        key=lambda node: (-len(node.unresolved_imports), node.path),
    )
    for node in unresolved[:2]:
        findings.append(
            ReportFinding(
                kind="unresolved_import",
                title="Unresolved local import",
                file_path=node.path,
                detail=f"{len(node.unresolved_imports)} relative imports could not be mapped: {', '.join(node.unresolved_imports[:3])}.",
                severity="medium",
                confidence="high",
                related_files=node.unresolved_imports,
            )
        )

    largest = sorted(nodes, key=lambda node: (-node.metrics.loc, node.path))[:1]
    for node in largest:
        if node.metrics.loc >= 80:
            findings.append(
                ReportFinding(
                    kind="large_file",
                    title="Large file",
                    file_path=node.path,
                    detail=f"{node.metrics.loc} LoC, {node.metrics.dependent_count} dependents, {node.metrics.dependency_count} dependencies.",
                    severity="medium",
                    confidence="high",
                )
            )

    complex_nodes = sorted(nodes, key=lambda node: (-node.metrics.complexity, node.path))[:1]
    for node in complex_nodes:
        if node.metrics.complexity >= 8:
            findings.append(
                ReportFinding(
                    kind="complex_file",
                    title="High branch complexity",
                    file_path=node.path,
                    detail=f"Complexity score {node.metrics.complexity} across {node.metrics.loc} LoC; likely to hide edge cases.",
                    severity="medium",
                    confidence="high",
                )
            )

    hubs = sorted(nodes, key=lambda node: (-node.metrics.dependent_count, node.path))[:2]
    for node in hubs:
        if node.metrics.dependent_count >= 2:
            facade = is_package_init(node.path)
            findings.append(
                ReportFinding(
                    kind="api_facade" if facade else "hub",
                    title="Public API facade" if facade else "High impact dependency",
                    file_path=node.path,
                    detail=hub_detail(node, facade),
                    severity="low" if facade else "medium",
                    confidence="medium" if facade else "high",
                    related_files=node.imported_by[:8],
                )
            )

    findings = dedupe_findings(findings)[:6]
    entry_points = find_entry_points(root, scanned_files)
    reading_order = list(
        dict.fromkeys(
            [entry.file_path for entry in entry_points]
            + [finding.file_path for finding in findings]
            + [node.path for node in sorted(nodes, key=lambda item: (-item.metrics.dependent_count, item.path))[:3]]
        )
    )
    orphans = find_orphans(nodes, entry_points)
    return RepoReport(start_here=findings, entry_points=entry_points[:8], reading_order=reading_order[:12], orphans=orphans[:10])


def find_orphans(nodes: list[GraphNode], entry_points: list[EntryPointSummary]) -> list[ReportFinding]:
    entry_paths = {entry.file_path for entry in entry_points}
    orphans: list[ReportFinding] = []
    for node in sorted(nodes, key=lambda item: (-item.metrics.loc, item.path)):
        if node.imported_by:
            continue
        if node.path in entry_paths or is_package_init(node.path) or is_test_path(node.path):
            continue
        orphans.append(
            ReportFinding(
                kind="orphan",
                title="Possibly unused file",
                file_path=node.path,
                detail=f"Nothing imports this file and it is not a detected entry point ({node.metrics.loc} LoC). It may be dead code or a manually run script.",
                severity="low",
                confidence="low",
            )
        )
    return orphans


def is_test_path(path: str) -> bool:
    relative = Path(path)
    parts = {part.lower() for part in relative.parts[:-1]}
    return is_test_like(parts, relative.name.lower())


def cycle_detail(files: list[str]) -> str:
    prefix = f"{len(files)} files import each other ({', '.join(files[:3])})"
    if any(is_package_init(path) for path in files):
        return f"{prefix}; package facade or lazy imports may inflate this cycle."
    return f"{prefix}; change these carefully."


def hub_detail(node: GraphNode, facade: bool) -> str:
    dependents = f"{node.metrics.dependent_count} files import this file; first dependents: {', '.join(node.imported_by[:3])}."
    if facade:
        return f"{dependents} This looks like a package API barrel, so treat it as public surface before calling it bad coupling."
    return dependents


def is_package_init(path: str) -> bool:
    return path.endswith("__init__.py")


def dedupe_findings(findings: list[ReportFinding]) -> list[ReportFinding]:
    seen: set[tuple[str, str]] = set()
    deduped = []
    for finding in findings:
        key = (finding.kind, finding.file_path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def find_entry_points(root: Path, files: list[ScannedFile]) -> list[EntryPointSummary]:
    entries = [entry for item in files if (entry := detect_entry_point(item))]
    entries.extend(find_metadata_entry_points(root, {item.relative_path: item for item in files}))
    seen: set[tuple[str, str]] = set()
    deduped = []
    for item in entries:
        key = (item.kind, item.file_path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return sorted(deduped, key=lambda entry: (entry.kind, entry.file_path))


def find_metadata_entry_points(root: Path, files: dict[str, ScannedFile]) -> list[EntryPointSummary]:
    entries: list[EntryPointSummary] = []
    entries.extend(find_package_json_entry_points(root, files))
    entries.extend(find_pyproject_entry_points(root, files))
    return entries


def find_package_json_entry_points(root: Path, files: dict[str, ScannedFile]) -> list[EntryPointSummary]:
    package_json = root / "package.json"
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    entries: list[EntryPointSummary] = []
    scripts = data.get("scripts", {})
    if isinstance(scripts, dict):
        for name, command in scripts.items():
            if isinstance(name, str) and isinstance(command, str):
                target = script_target(command, files)
                if target:
                    entries.append(EntryPointSummary(kind="package_script", file_path=target, label=f"Package script: {name}", detail=f"`npm run {name}` reaches this file."))
    bin_field = data.get("bin", {})
    if isinstance(bin_field, str):
        target = first_existing_candidate(bin_field, files)
        if target:
            entries.append(EntryPointSummary(kind="package_bin", file_path=target, label="Package bin", detail="Declared as the package executable."))
    elif isinstance(bin_field, dict):
        for name, path in bin_field.items():
            if isinstance(name, str) and isinstance(path, str):
                target = first_existing_candidate(path, files)
                if target:
                    entries.append(EntryPointSummary(kind="package_bin", file_path=target, label=f"Package bin: {name}", detail="Declared as a package executable."))
    return entries


def find_pyproject_entry_points(root: Path, files: dict[str, ScannedFile]) -> list[EntryPointSummary]:
    pyproject = root / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []

    scripts = data.get("project", {}).get("scripts", {})
    if not isinstance(scripts, dict):
        return []
    entries = []
    for name, target in scripts.items():
        if not isinstance(name, str) or not isinstance(target, str):
            continue
        module = target.split(":", 1)[0].replace(".", "/")
        file_path = first_existing_candidate(module, files, python=True) or first_existing_candidate(f"src/{module}", files, python=True)
        if file_path:
            entries.append(EntryPointSummary(kind="python_script", file_path=file_path, label=f"Python script: {name}", detail=f"`{name}` resolves to `{target}`."))
    return entries


def script_target(command: str, files: dict[str, ScannedFile]) -> str | None:
    match = re.search(r"(?:node|tsx|ts-node|vite-node|python(?:3)?)\s+([^\s;&|]+)", command)
    if not match:
        return None
    return first_existing_candidate(match.group(1), files)


def detect_entry_point(item: ScannedFile) -> EntryPointSummary | None:
    text = item.text
    if item.extension == ".py":
        if 'if __name__ == "__main__"' in text or "if __name__ == '__main__'" in text:
            return entry(item, "python_cli", "Likely Python CLI", "Contains a Python main guard.")
        if "FastAPI(" in text:
            return entry(item, "python_web", "Likely FastAPI app", "Defines a FastAPI app or route.")
        if re.search(r"@\w+\.(get|post|put|patch|delete)\(", text):
            return entry(item, "python_web", "Likely Python web routes", "Defines web route handlers.")
        if "Flask(" in text or "@app.route(" in text:
            return entry(item, "python_web", "Likely Flask app", "Defines a Flask app or route.")
    if item.extension in {".js", ".jsx", ".ts", ".tsx"}:
        if "createRoot(" in text or "ReactDOM.render(" in text:
            return entry(item, "react_root", "Likely React root", "Mounts the React application.")
    if item.extension in {".c", ".cc", ".cpp"} and re.search(r"\bint\s+main\s*\(", text):
        return entry(item, "native_main", "Likely native entry point", "Defines a C/C++ main function.")
    return None


def entry(item: ScannedFile, kind: str, label: str, detail: str) -> EntryPointSummary:
    return EntryPointSummary(kind=kind, file_path=item.relative_path, label=label, detail=detail)


def build_folder_summaries(nodes: list[GraphNode]) -> list[FolderSummary]:
    summaries: dict[str, dict[str, int]] = defaultdict(lambda: {"files": 0, "loc": 0})
    for node in nodes:
        name = node.folder.split("/", 1)[0] if node.folder else "root"
        summaries[name]["files"] += 1
        summaries[name]["loc"] += node.metrics.loc
    return sorted(
        (FolderSummary(name=name, **summary) for name, summary in summaries.items()),
        key=lambda item: (-item.loc, -item.files, item.name),
    )


def find_cycles(nodes: list[GraphNode], edges: list[GraphEdge]) -> list[CycleSummary]:
    node_ids = {node.id for node in nodes}
    graph = {node_id: [] for node_id in node_ids}
    self_loops: set[str] = set()
    for edge in edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            continue
        graph[edge.source].append(edge.target)
        if edge.source == edge.target:
            self_loops.add(edge.source)

    index = 0
    stack: list[str] = []
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def strongconnect(node_id: str) -> None:
        nonlocal index
        indexes[node_id] = index
        lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)

        for target in graph[node_id]:
            if target not in indexes:
                strongconnect(target)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[target])
            elif target in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indexes[target])

        if lowlinks[node_id] != indexes[node_id]:
            return

        component = []
        while True:
            current = stack.pop()
            on_stack.remove(current)
            component.append(current)
            if current == node_id:
                break
        if len(component) > 1 or component[0] in self_loops:
            components.append(sorted(component))

    for node_id in sorted(node_ids):
        if node_id not in indexes:
            strongconnect(node_id)

    component_by_node = {node_id: index for index, component in enumerate(components) for node_id in component}
    edge_counts = [0] * len(components)
    for edge in edges:
        source_component = component_by_node.get(edge.source)
        if source_component is not None and source_component == component_by_node.get(edge.target):
            edge_counts[source_component] += 1

    cycles = [CycleSummary(files=component, edge_count=edge_counts[index]) for index, component in enumerate(components)]
    return sorted(cycles, key=lambda item: (-len(item.files), -item.edge_count, item.files[0]))


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
        resolved = first_existing_candidate(candidate.as_posix(), files, python=True)
        if resolved:
            return resolved
        if module and "." not in module:
            return first_existing_candidate((base / "__init__").as_posix(), files, python=True)
        return None

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
