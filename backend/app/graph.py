from __future__ import annotations

import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import posixpath
import re
import tomllib
from pathlib import Path

from app.git_history import GitHistory, collect_git_history, recency_days
from app.models import (
    AnalyzeRequest,
    CodeHint,
    CycleSummary,
    EdgeKind,
    EntryPointSummary,
    FileGitStats,
    FileMetrics,
    FolderSummary,
    GitSummary,
    GraphEdge,
    GraphNode,
    GraphResponse,
    GraphStats,
    PackageEdge,
    PackageSummary,
    RepoReport,
    ReportFinding,
    RouteSummary,
    SubgraphRequest,
)
from app.parsers import Dependency, parse_dependencies, parse_symbols
from app.scanner import ScannedFile, scan_repository

RESOLUTION_EXTENSIONS = ["", ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".c", ".h", ".cc", ".cpp", ".hpp", ".go", ".java", ".rb", ".rs", ".php", "/index.js", "/index.ts", "/__init__.py", "/mod.rs"]
AWS_KEY_PATTERN = re.compile(r"AKIA[0-9A-Z]{16}")
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----")
SECRET_ASSIGNMENT_PATTERN = re.compile(r"(?i)(api_key|apikey|secret|password|passwd|private_key)\s*[:=]\s*['\"][0-9A-Za-z_\-]{16,}['\"]")
UNSAFE_API_PATTERN = re.compile(r"\beval\s*\(|\bexec\s*\(|os\.system\s*\(|shell\s*=\s*True|child_process\.exec\s*\(|dangerouslySetInnerHTML|\bgets\s*\(|\bstrcpy\s*\(")


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
            symbols=parse_symbols(item.relative_path, item.text),
            hints=detect_file_hints(item),
        )
        for item in scanned_files
    }
    edges: list[GraphEdge] = []
    edge_ids: set[str] = set()

    for item in scanned_files:
        for dep in parse_dependencies(item.relative_path, item.text):
            target = resolve_dependency(item, dep, by_path, ts_aliases)
            if target:
                edge_id = f"{item.relative_path}->{target}:{dep.kind.value}:{dep.scope.value}"
                if edge_id in edge_ids:
                    continue
                edge_ids.add(edge_id)
                edge = GraphEdge(
                    id=edge_id,
                    source=item.relative_path,
                    target=target,
                    kind=dep.kind,
                    label=f"{dep.kind.value.replace('_', ' ')} / {dep.scope.value.replace('_', ' ')}",
                    scope=dep.scope,
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

    history = collect_git_history(root, {node.path for node in sorted_nodes})
    attach_git_stats(sorted_nodes, history)
    for node in sorted_nodes:
        node.metrics.risk_score = calculate_risk_score(node)

    folder_summaries = build_folder_summaries(sorted_nodes)
    package_summaries = build_package_summaries(sorted_nodes, history)
    package_edges = build_package_edges(sorted_nodes)
    routes = extract_routes(scanned_files)
    cycles = find_cycles(sorted_nodes, sorted_edges)

    return GraphResponse(
        root_path=str(root.resolve()),
        nodes=sorted_nodes,
        edges=sorted_edges,
        folder_summaries=folder_summaries,
        package_summaries=package_summaries,
        package_edges=package_edges,
        routes=routes,
        cycles=cycles,
        repo_report=build_repo_report(root, sorted_nodes, cycles, scanned_files),
        git=GitSummary(
            available=history.available,
            total_commits=history.total_commits,
            capped=history.capped,
            note=history.note,
        ),
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


def build_subgraph(root: Path, request: SubgraphRequest) -> GraphResponse:
    return slice_subgraph(build_graph(root, request), request)


def slice_subgraph(graph: GraphResponse, request: SubgraphRequest) -> GraphResponse:
    node_ids = {node.id for node in graph.nodes}
    if request.focus_path not in node_ids:
        raise ValueError(f"focus_path is not in the analyzed graph: {request.focus_path}")

    keep = {request.focus_path}
    frontier = {request.focus_path}
    for _ in range(request.depth):
        next_frontier: set[str] = set()
        for edge in graph.edges:
            if edge.source in frontier:
                next_frontier.add(edge.target)
            if edge.target in frontier:
                next_frontier.add(edge.source)
        next_frontier -= keep
        keep |= next_frontier
        frontier = next_frontier
        if not frontier:
            break

    nodes = [node.model_copy(deep=True) for node in graph.nodes if node.id in keep]
    edges = [edge for edge in graph.edges if edge.source in keep and edge.target in keep]
    for node in nodes:
        node.imports = [path for path in node.imports if path in keep]
        node.imported_by = [path for path in node.imported_by if path in keep]
        node.metrics.dependency_count = len(node.imports)
        node.metrics.dependent_count = len(node.imported_by)
    warnings = [*graph.stats.warnings, f"Backend subgraph centered on {request.focus_path} with depth {request.depth}."]
    return graph.model_copy(
        update={
            "nodes": nodes,
            "edges": edges,
            "folder_summaries": build_folder_summaries(nodes),
            "package_summaries": build_package_summaries(nodes),
            "package_edges": build_package_edges(nodes),
            "routes": [route for route in graph.routes if route.file_path in keep],
            "cycles": [cycle for cycle in graph.cycles if set(cycle.files) <= keep],
            "repo_report": RepoReport(),
            "stats": GraphStats(
                total_files_found=graph.stats.total_files_found,
                analyzed_files=len(nodes),
                skipped_files=graph.stats.skipped_files,
                skipped_reasons=graph.stats.skipped_reasons,
                truncated=graph.stats.truncated,
                warnings=warnings,
            ),
        }
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

    risky_nodes = sorted(nodes, key=lambda node: (-node.metrics.risk_score, node.path))[:1]
    for node in risky_nodes:
        if node.metrics.risk_score >= 60:
            findings.append(
                ReportFinding(
                    kind="risk",
                    title="High risk file",
                    file_path=node.path,
                    detail=f"Risk score {node.metrics.risk_score}/100 from size, complexity, coupling, and unresolved imports.",
                    severity="high" if node.metrics.risk_score >= 80 else "medium",
                    confidence="medium",
                )
            )

    hinted_nodes = sorted(
        (node for node in nodes if node.hints),
        key=lambda node: (hint_severity_rank(node.hints[0].severity), node.path),
    )
    for node in hinted_nodes[:2]:
        hint = node.hints[0]
        findings.append(
            ReportFinding(
                kind=hint.kind,
                title=hint.title,
                file_path=node.path,
                detail=hint.detail,
                severity=hint.severity,
                confidence="medium",
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

    entry_points = find_entry_points(root, scanned_files)
    entry_paths = {entry.file_path for entry in entry_points}
    findings.extend(churn_findings(nodes))
    findings.extend(dead_code_findings(nodes, entry_paths))

    findings = sorted(dedupe_findings(findings), key=finding_rank)[:6]
    reading_order = list(
        dict.fromkeys(
            [entry.file_path for entry in entry_points]
            + [finding.file_path for finding in findings]
            + [node.path for node in sorted(nodes, key=lambda item: (-item.metrics.risk_score, item.path))[:3]]
        )
    )
    orphans = find_orphans(nodes, entry_paths)
    return RepoReport(start_here=findings, entry_points=entry_points[:8], reading_order=reading_order[:12], orphans=orphans[:10])


def find_orphans(nodes: list[GraphNode], entry_paths: set[str]) -> list[ReportFinding]:
    orphans: list[ReportFinding] = []
    for node in sorted(nodes, key=lambda item: (-item.metrics.loc, item.path)):
        if node.imported_by or node.path in entry_paths or is_package_init(node.path) or is_test_path(node.path):
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


SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}


def finding_rank(finding: ReportFinding) -> tuple[int, int, str]:
    return (SEVERITY_RANK.get(finding.severity, 3), CONFIDENCE_RANK.get(finding.confidence, 3), finding.file_path)


def churn_findings(nodes: list[GraphNode]) -> list[ReportFinding]:
    scored = [node for node in nodes if node.git and (node.git.fix_commits or node.git.churn)]
    if not scored:
        return []
    top = max(scored, key=lambda node: (node.git.fix_commits, node.git.churn, -node.metrics.risk_score))
    git = top.git
    recency = f"last touched {git.recency_days} days ago" if git.recency_days is not None else "recently touched"
    bug = f", {git.fix_commits} bug-fix commits" if git.fix_commits else ""
    return [
        ReportFinding(
            kind="churn_hotspot",
            title="Frequently changed file",
            file_path=top.path,
            detail=f"{git.commits} commits{bug}, {git.churn} lines churned; {recency}. Change-prone code is where regressions cluster.",
            severity="high" if git.fix_commits else "medium",
            confidence="high",
            related_files=top.imported_by[:8],
        )
    ]


def dead_code_findings(nodes: list[GraphNode], entry_paths: set[str]) -> list[ReportFinding]:
    candidates = [
        node
        for node in nodes
        if node.metrics.dependent_count == 0
        and node.path not in entry_paths
        and not is_package_init(node.path)
        and not is_test_path(node.path)
    ]
    candidates.sort(key=lambda node: (-node.metrics.loc, node.path))
    findings = []
    for node in candidates[:2]:
        if node.metrics.loc < 20:
            continue
        findings.append(
            ReportFinding(
                kind="dead_code_candidate",
                title="Possibly unused file",
                file_path=node.path,
                detail=f"{node.metrics.loc} LoC with no local importers. Candidate only - entry scripts, framework routes, and dynamically loaded modules can look unused.",
                severity="low",
                confidence="medium",
            )
        )
    return findings


def is_test_path(path: str) -> bool:
    lower = path.lower()
    name = Path(lower).name
    if any(part in {"tests", "test", "__tests__", "spec", "specs"} for part in lower.split("/")[:-1]):
        return True
    stem = Path(name).stem
    return name.startswith("test_") or stem.endswith("_test") or stem.endswith(".test") or stem.endswith(".spec")


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
    if item.extension in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        if "createRoot(" in text or "ReactDOM.render(" in text:
            return entry(item, "react_root", "Likely React root", "Mounts the React application.")
    if item.extension in {".c", ".cc", ".cpp"} and re.search(r"\bint\s+main\s*\(", text):
        return entry(item, "native_main", "Likely native entry point", "Defines a C/C++ main function.")
    if item.extension == ".go" and re.search(r"\bfunc\s+main\s*\(", text):
        return entry(item, "go_main", "Likely Go entry point", "Defines a Go main function.")
    if item.extension == ".java" and re.search(r"public\s+static\s+void\s+main\s*\(", text):
        return entry(item, "java_main", "Likely Java entry point", "Defines a Java main method.")
    if item.extension == ".rs" and re.search(r"\bfn\s+main\s*\(", text):
        return entry(item, "rust_main", "Likely Rust entry point", "Defines a Rust main function.")
    return None


def entry(item: ScannedFile, kind: str, label: str, detail: str) -> EntryPointSummary:
    return EntryPointSummary(kind=kind, file_path=item.relative_path, label=label, detail=detail)


JS_ROUTE = re.compile(r"""\b(?:app|router)\.(get|post|put|patch|delete|all)\(\s*['"]([^'"]+)['"]""")
SPRING_ROUTE = re.compile(r"""@(Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*|path\s*=\s*)?['"]([^'"]+)['"]""")
GO_ROUTE = re.compile(r"""\b\w+\.(GET|POST|PUT|PATCH|DELETE|Handle|HandleFunc)\(\s*['"]([^'"]+)['"]""")
LARAVEL_ROUTE = re.compile(r"""Route::(get|post|put|patch|delete|any)\(\s*['"]([^'"]+)['"]""")
RAILS_ROUTE = re.compile(r"""^\s*(get|post|put|patch|delete)\s+['"]([^'"]+)['"]""", re.MULTILINE)


def extract_routes(files: list[ScannedFile]) -> list[RouteSummary]:
    routes: list[RouteSummary] = []
    for item in files:
        text = item.text
        if item.extension == ".py":
            routes.extend(extract_python_routes(text, item.relative_path))
        elif item.extension in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
            routes.extend(RouteSummary(method=match.group(1).upper(), path=match.group(2), file_path=item.relative_path, framework="express") for match in JS_ROUTE.finditer(text))
        elif item.extension == ".java":
            routes.extend(RouteSummary(method="ANY" if match.group(1) == "Request" else match.group(1).upper(), path=match.group(2), file_path=item.relative_path, framework="spring") for match in SPRING_ROUTE.finditer(text))
        elif item.extension == ".go":
            routes.extend(RouteSummary(method="ANY" if match.group(1).startswith("Handle") else match.group(1), path=match.group(2), file_path=item.relative_path, framework="go-http") for match in GO_ROUTE.finditer(text))
        elif item.extension == ".php":
            routes.extend(RouteSummary(method=match.group(1).upper(), path=match.group(2), file_path=item.relative_path, framework="laravel") for match in LARAVEL_ROUTE.finditer(text))
        elif item.extension == ".rb":
            routes.extend(RouteSummary(method=match.group(1).upper(), path=match.group(2), file_path=item.relative_path, framework="rails") for match in RAILS_ROUTE.finditer(text))
    return sorted(routes, key=lambda route: (route.file_path, route.path, route.method))[:200]


def extract_python_routes(text: str, file_path: str) -> list[RouteSummary]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    routes: list[RouteSummary] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                route = python_decorator_route(decorator, file_path)
                if route:
                    routes.append(route)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"path", "re_path", "url"}:
            path = first_string_arg(node)
            if path:
                routes.append(RouteSummary(method="ANY", path=path, file_path=file_path, framework="django"))
    return routes


def python_decorator_route(node: ast.AST, file_path: str) -> RouteSummary | None:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    path = first_string_arg(node)
    if not path:
        return None
    method = node.func.attr.lower()
    if method == "route":
        return RouteSummary(method=route_methods(node), path=path, file_path=file_path, framework="flask")
    if method in {"get", "post", "put", "patch", "delete", "websocket"}:
        return RouteSummary(method=method.upper(), path=path, file_path=file_path, framework="python")
    return None


def first_string_arg(node: ast.Call) -> str | None:
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    return None


def route_methods(node: ast.Call) -> str:
    for keyword in node.keywords:
        if keyword.arg != "methods":
            continue
        if isinstance(keyword.value, ast.List):
            methods = [item.value.upper() for item in keyword.value.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
            return ",".join(methods) if methods else "GET"
    return "GET"


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


def build_package_summaries(nodes: list[GraphNode], history: GitHistory | None = None) -> list[PackageSummary]:
    history = history or GitHistory.unavailable("")
    grouped: dict[str, list[GraphNode]] = defaultdict(list)
    for node in nodes:
        grouped[top_package(node.path)].append(node)

    summaries = []
    for name, package_nodes in grouped.items():
        dependencies = {dep for node in package_nodes for dep in node.imports if top_package(dep) != name}
        dependents = {dep for node in package_nodes for dep in node.imported_by if top_package(dep) != name}
        highest_risk = sorted(package_nodes, key=lambda node: (-node.metrics.risk_score, node.path))[:3]
        primary_author, bus_factor = package_ownership(package_nodes, history)
        summaries.append(
            PackageSummary(
                name=name,
                files=len(package_nodes),
                loc=sum(node.metrics.loc for node in package_nodes),
                average_complexity=round(sum(node.metrics.complexity for node in package_nodes) / len(package_nodes), 2),
                average_risk=round(sum(node.metrics.risk_score for node in package_nodes) / len(package_nodes), 2),
                dependency_count=len(dependencies),
                dependent_count=len(dependents),
                highest_risk_files=[node.path for node in highest_risk if node.metrics.risk_score > 0],
                bus_factor=bus_factor,
                primary_author=primary_author,
                churn=sum(node.git.churn if node.git else 0 for node in package_nodes),
            )
        )
    return sorted(summaries, key=lambda item: (-item.average_risk, -item.loc, item.name))


def top_package(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else "root"


def calculate_risk_score(node: GraphNode) -> int:
    score = 0
    score += min(node.metrics.loc // 10, 25)
    score += min(node.metrics.complexity * 3, 30)
    score += min(node.metrics.dependent_count * 5, 20)
    score += min(node.metrics.dependency_count * 3, 10)
    score += min(len(node.unresolved_imports) * 10, 15)
    score += min(sum(12 for hint in node.hints if hint.kind == "security"), 20)
    if node.git:
        # Change-prone code is where regressions cluster; weight churn and the
        # number of past bug-fix commits as real, history-backed risk.
        score += min(node.git.churn // 50, 15)
        score += min(node.git.fix_commits * 5, 15)
    return min(score, 100)


def attach_git_stats(nodes: list[GraphNode], history: GitHistory) -> None:
    for node in nodes:
        record = history.files.get(node.path)
        if record is None:
            continue
        primary_author, share = record.primary()
        node.git = FileGitStats(
            commits=record.commits,
            churn=record.churn,
            fix_commits=record.fix_commits,
            distinct_authors=record.distinct_authors,
            primary_author=primary_author,
            primary_author_share=round(share, 3),
            last_modified=record.last_modified,
            recency_days=recency_days(record.last_modified),
        )


def package_ownership(package_nodes: list[GraphNode], history: GitHistory) -> tuple[str | None, int | None]:
    if not history.available:
        return None, None
    authors: Counter[str] = Counter()
    for node in package_nodes:
        record = history.files.get(node.path)
        if record:
            authors.update(record.authors)
    if not authors:
        return None, None
    total = sum(authors.values())
    ordered = authors.most_common()
    accumulated = 0
    bus_factor = 0
    for _author, count in ordered:
        accumulated += count
        bus_factor += 1
        if accumulated * 2 > total:
            break
    return ordered[0][0], bus_factor


def build_package_edges(nodes: list[GraphNode]) -> list[PackageEdge]:
    package_of = {node.path: top_package(node.path) for node in nodes}
    counts: Counter[tuple[str, str]] = Counter()
    for node in nodes:
        source = package_of[node.path]
        for target_path in node.imports:
            target = package_of.get(target_path)
            if target is not None and target != source:
                counts[(source, target)] += 1
    return [
        PackageEdge(source=source, target=target, count=count)
        for (source, target), count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def detect_file_hints(item: ScannedFile) -> list[CodeHint]:
    hints = detect_security_hints(item)
    hints.extend(detect_framework_hints(item))
    return sorted(hints, key=lambda hint: (hint_severity_rank(hint.severity), hint.line or 0, hint.title))[:8]


def detect_security_hints(item: ScannedFile) -> list[CodeHint]:
    hints: list[CodeHint] = []
    for line_number, line in enumerate(item.text.splitlines(), start=1):
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped or lower.startswith(("#", "//")):
            continue
        if "placeholder" in lower or "example" in lower or "your_" in lower or ("<" in stripped and ">" in stripped):
            continue
        if AWS_KEY_PATTERN.search(stripped) or PRIVATE_KEY_PATTERN.search(stripped):
            hints.append(CodeHint(kind="security", title="Secret-like value", detail="A credential or private key pattern appears in source.", severity="high", line=line_number))
        elif SECRET_ASSIGNMENT_PATTERN.search(stripped):
            hints.append(CodeHint(kind="security", title="Hardcoded secret candidate", detail="A secret-looking assignment appears in source.", severity="high", line=line_number))
        elif UNSAFE_API_PATTERN.search(stripped):
            hints.append(CodeHint(kind="security", title="Unsafe API pattern", detail="A risky execution, shell, DOM, or memory API appears in source.", severity="medium", line=line_number))
    return hints


def detect_framework_hints(item: ScannedFile) -> list[CodeHint]:
    text = item.text
    hints: list[CodeHint] = []
    if item.extension == ".py":
        if "FastAPI(" in text or "APIRouter(" in text:
            hints.append(CodeHint(kind="framework", title="FastAPI surface", detail="Defines a FastAPI app or router.", severity="low"))
        if "Flask(" in text or "@app.route(" in text or "@bp.route(" in text:
            hints.append(CodeHint(kind="framework", title="Flask surface", detail="Defines a Flask app, blueprint, or route.", severity="low"))
        if "urlpatterns" in text or "INSTALLED_APPS" in text or "ROOT_URLCONF" in text:
            hints.append(CodeHint(kind="framework", title="Django configuration surface", detail="Defines Django URL, settings, or app configuration.", severity="low"))
    if item.extension in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        if "createRoot(" in text or "ReactDOM.render(" in text:
            hints.append(CodeHint(kind="framework", title="React root", detail="Mounts the React application.", severity="low"))
        if "express(" in text or ".get(" in text and "req" in text and "res" in text:
            hints.append(CodeHint(kind="framework", title="Node route surface", detail="Looks like an Express-style route file.", severity="low"))
    if item.extension == ".go" and ("http.HandleFunc(" in text or ".GET(" in text or ".POST(" in text):
        hints.append(CodeHint(kind="framework", title="Go HTTP surface", detail="Registers Go HTTP routes or handlers.", severity="low"))
    if item.extension == ".java" and ("@RestController" in text or "@RequestMapping" in text or "@GetMapping" in text or "@SpringBootApplication" in text):
        hints.append(CodeHint(kind="framework", title="Spring surface", detail="Defines a Spring controller or application.", severity="low"))
    if item.extension == ".rb" and ("Rails.application" in text or "< ApplicationController" in text):
        hints.append(CodeHint(kind="framework", title="Rails surface", detail="Defines a Rails app or controller.", severity="low"))
    if item.extension == ".php" and ("Route::" in text or "extends Controller" in text or "Illuminate\\" in text):
        hints.append(CodeHint(kind="framework", title="Laravel surface", detail="Defines Laravel routes or a controller.", severity="low"))
    if item.extension == ".rs" and ("HttpServer::new" in text or "Router::new" in text or "actix_web" in text or "axum::" in text):
        hints.append(CodeHint(kind="framework", title="Rust web surface", detail="Registers Actix or Axum routes.", severity="low"))
    return hints


def hint_severity_rank(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(severity, 3)


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
    if source.extension in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        if dependency.is_relative:
            return resolve_path_like_dependency(source, dependency.raw, files)
        return resolve_ts_alias_dependency(dependency.raw, files, ts_aliases or [])
    if source.extension in {".c", ".h", ".cc", ".cpp", ".hpp"} and dependency.is_relative:
        return resolve_path_like_dependency(source, dependency.raw, files)
    if source.extension == ".go":
        return resolve_go_dependency(dependency, files)
    if source.extension == ".java":
        return resolve_java_dependency(dependency, files)
    if source.extension == ".rb":
        return resolve_path_like_dependency(source, dependency.raw, files) if dependency.is_relative else first_existing_candidate(dependency.raw, files) or first_existing_candidate(f"lib/{dependency.raw}", files)
    if source.extension == ".rs":
        return resolve_rust_dependency(source, dependency, files)
    if source.extension == ".php" and dependency.is_relative:
        return resolve_path_like_dependency(source, dependency.raw.lstrip("./"), files)
    return None


def resolve_go_dependency(dependency: Dependency, files: dict[str, ScannedFile]) -> str | None:
    go_files = sorted(path for path in files if path.endswith(".go"))
    for start in range(len(dependency.raw.split("/"))):
        suffix = "/".join(dependency.raw.split("/")[start:])
        for path in go_files:
            folder = posixpath.dirname(path)
            if folder == suffix or folder.endswith("/" + suffix):
                return path
    return None


def resolve_java_dependency(dependency: Dependency, files: dict[str, ScannedFile]) -> str | None:
    if dependency.raw.endswith(".*"):
        return None
    target = dependency.raw.replace(".", "/") + ".java"
    return next((path for path in files if path == target or path.endswith("/" + target)), None)


def resolve_rust_dependency(source: ScannedFile, dependency: Dependency, files: dict[str, ScannedFile]) -> str | None:
    base = Path(source.relative_path).parent
    raw = dependency.raw
    if "::" not in raw:
        return first_existing_candidate((base / raw).as_posix(), files) or first_existing_candidate((base / raw / "mod").as_posix(), files)
    head, *rest = raw.split("::")
    sub = "/".join(rest)
    if not sub:
        return None
    if head == "crate":
        return first_existing_candidate(f"src/{sub}", files) or first_existing_candidate(f"src/{sub}/mod", files) or first_existing_candidate(sub, files)
    if head in {"self", "super"}:
        anchor = base if head == "self" else base.parent
        return first_existing_candidate((anchor / sub).as_posix(), files) or first_existing_candidate((anchor / sub / "mod").as_posix(), files)
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
