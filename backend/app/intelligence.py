from __future__ import annotations

from collections import Counter, defaultdict

from app.git_history import GitHistory, recency_days
from app.models import (
    FileGitStats,
    GraphEdge,
    GraphNode,
    PackageEdge,
    PackageSummary,
)

# Risk weights. Two profiles: one when git history is available (churn and
# bug-fix frequency carry real signal) and one for static-only repos where that
# weight is redistributed onto the structural metrics we do have.
RISK_WEIGHTS_WITH_GIT = {"complexity": 0.25, "loc": 0.15, "coupling": 0.20, "churn": 0.25, "fix": 0.15}
RISK_WEIGHTS_STATIC = {"complexity": 0.40, "loc": 0.25, "coupling": 0.35}


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


def attach_risk_scores(nodes: list[GraphNode], git_available: bool) -> None:
    if not nodes:
        return
    weights = RISK_WEIGHTS_WITH_GIT if git_available else RISK_WEIGHTS_STATIC
    max_loc = max((node.metrics.loc for node in nodes), default=0)
    max_complexity = max((node.metrics.complexity for node in nodes), default=0)
    max_coupling = max((node.metrics.dependent_count for node in nodes), default=0)
    max_churn = max((node.git.churn if node.git else 0 for node in nodes), default=0)
    max_fix = max((node.git.fix_commits if node.git else 0 for node in nodes), default=0)

    for node in nodes:
        signals = {
            "complexity": _ratio(node.metrics.complexity, max_complexity),
            "loc": _ratio(node.metrics.loc, max_loc),
            "coupling": _ratio(node.metrics.dependent_count, max_coupling),
            "churn": _ratio(node.git.churn if node.git else 0, max_churn),
            "fix": _ratio(node.git.fix_commits if node.git else 0, max_fix),
        }
        score = sum(weights.get(name, 0.0) * value for name, value in signals.items())
        node.risk = round(100 * score, 1)


def build_packages(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    history: GitHistory,
) -> tuple[list[PackageSummary], list[PackageEdge]]:
    package_of = {node.path: package_name(node.folder) for node in nodes}
    grouped: dict[str, list[GraphNode]] = defaultdict(list)
    for node in nodes:
        grouped[package_of[node.path]].append(node)

    cross_counts: Counter[tuple[str, str]] = Counter()
    internal_counts: Counter[str] = Counter()
    for edge in edges:
        source = package_of.get(edge.source)
        target = package_of.get(edge.target)
        if source is None or target is None:
            continue
        if source == target:
            internal_counts[source] += 1
        else:
            cross_counts[(source, target)] += 1

    incoming: Counter[str] = Counter()
    outgoing: Counter[str] = Counter()
    for (source, target), count in cross_counts.items():
        outgoing[source] += count
        incoming[target] += count

    summaries: list[PackageSummary] = []
    for name, members in grouped.items():
        author, bus_factor = package_ownership(members, history)
        summaries.append(
            PackageSummary(
                name=name,
                files=len(members),
                loc=sum(member.metrics.loc for member in members),
                complexity=sum(member.metrics.complexity for member in members),
                risk=round(max((member.risk for member in members), default=0.0), 1),
                internal_edges=internal_counts.get(name, 0),
                incoming_edges=incoming.get(name, 0),
                outgoing_edges=outgoing.get(name, 0),
                bus_factor=bus_factor,
                primary_author=author,
                churn=sum(member.git.churn if member.git else 0 for member in members),
            )
        )

    summaries.sort(key=lambda item: (-item.risk, -item.loc, item.name))
    package_edges = [
        PackageEdge(source=source, target=target, count=count)
        for (source, target), count in sorted(cross_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return summaries, package_edges


def package_ownership(members: list[GraphNode], history: GitHistory) -> tuple[str | None, int | None]:
    if not history.available:
        return None, None
    authors: Counter[str] = Counter()
    for member in members:
        record = history.files.get(member.path)
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


def package_name(folder: str) -> str:
    # A package is the file's directory. Grouping by the full folder keeps
    # src/<pkg> layouts and deep trees meaningful instead of collapsing them
    # all into one top-level bucket.
    return folder or "(root)"


def _ratio(value: int, maximum: int) -> float:
    if maximum <= 0:
        return 0.0
    return value / maximum
