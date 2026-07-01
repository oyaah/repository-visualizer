from __future__ import annotations

from pathlib import Path
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class NodeKind(str, Enum):
    FILE = "file"


class EdgeKind(str, Enum):
    IMPORT = "import"
    INCLUDE = "include"
    DYNAMIC_IMPORT = "dynamic_import"


class EdgeScope(str, Enum):
    TOP_LEVEL = "top_level"
    LAZY = "lazy"
    CONDITIONAL = "conditional"
    TYPE_CHECKING = "type_checking"
    RE_EXPORT = "re_export"
    DYNAMIC = "dynamic"


class AnalyzeRequest(BaseModel):
    root_path: str = Field(..., min_length=1)
    max_files: int = Field(default=1000, ge=1, le=10000)
    include_tests: bool = True
    include_vendor: bool = False

    @field_validator("root_path")
    @classmethod
    def expand_path(cls, value: str) -> str:
        return str(Path(value).expanduser())


class FileMetrics(BaseModel):
    loc: int
    total_lines: int
    size_bytes: int
    complexity: int
    maintainability: float = 100.0
    risk_score: int = 0
    dependency_count: int = 0
    dependent_count: int = 0


class FileGitStats(BaseModel):
    commits: int
    churn: int
    fix_commits: int
    distinct_authors: int
    primary_author: str | None = None
    primary_author_share: float = 0.0
    last_modified: str | None = None
    recency_days: int | None = None


class CodeSymbol(BaseModel):
    name: str
    kind: str
    line: int
    complexity: int


class CodeHint(BaseModel):
    kind: str
    title: str
    detail: str
    severity: str
    line: int | None = None


class GraphNode(BaseModel):
    id: str
    path: str
    label: str
    folder: str
    extension: str
    kind: NodeKind = NodeKind.FILE
    metrics: FileMetrics
    imports: list[str] = Field(default_factory=list)
    imported_by: list[str] = Field(default_factory=list)
    unresolved_imports: list[str] = Field(default_factory=list)
    external_imports: list[str] = Field(default_factory=list)
    symbols: list[CodeSymbol] = Field(default_factory=list)
    hints: list[CodeHint] = Field(default_factory=list)
    git: FileGitStats | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: EdgeKind
    label: str
    scope: EdgeScope = EdgeScope.TOP_LEVEL


class GraphStats(BaseModel):
    total_files_found: int
    analyzed_files: int
    skipped_files: int
    skipped_reasons: dict[str, int] = Field(default_factory=dict)
    truncated: bool
    warnings: list[str] = Field(default_factory=list)


class FolderSummary(BaseModel):
    name: str
    files: int
    loc: int


class PackageSummary(BaseModel):
    name: str
    files: int
    loc: int
    average_complexity: float
    average_risk: float
    dependency_count: int
    dependent_count: int
    highest_risk_files: list[str] = Field(default_factory=list)
    bus_factor: int | None = None
    primary_author: str | None = None
    churn: int = 0


class PackageEdge(BaseModel):
    source: str
    target: str
    count: int


class GitSummary(BaseModel):
    available: bool
    total_commits: int = 0
    capped: bool = False
    note: str | None = None


class CycleSummary(BaseModel):
    files: list[str]
    edge_count: int


class ReportFinding(BaseModel):
    kind: str
    title: str
    file_path: str
    detail: str
    severity: str
    confidence: str = "medium"
    related_files: list[str] = Field(default_factory=list)


class EntryPointSummary(BaseModel):
    kind: str
    file_path: str
    label: str
    detail: str


class RepoReport(BaseModel):
    start_here: list[ReportFinding] = Field(default_factory=list)
    entry_points: list[EntryPointSummary] = Field(default_factory=list)
    reading_order: list[str] = Field(default_factory=list)


class GraphResponse(BaseModel):
    root_path: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    folder_summaries: list[FolderSummary] = Field(default_factory=list)
    package_summaries: list[PackageSummary] = Field(default_factory=list)
    package_edges: list[PackageEdge] = Field(default_factory=list)
    cycles: list[CycleSummary] = Field(default_factory=list)
    repo_report: RepoReport = Field(default_factory=RepoReport)
    git: GitSummary = Field(default_factory=lambda: GitSummary(available=False))
    ignored_directories: list[str]
    stats: GraphStats


class SummaryRequest(BaseModel):
    root_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    model: str | None = None
    cache_only: bool = False

    @field_validator("root_path")
    @classmethod
    def expand_root(cls, value: str) -> str:
        return str(Path(value).expanduser())


class SummaryResponse(BaseModel):
    file_path: str
    summary: str | None
    cached: bool
    disabled: bool = False
    requires_generation: bool = False
    error: str | None = None
    content_hash: str | None = None
    model: str | None = None
