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
    dependency_count: int = 0
    dependent_count: int = 0


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


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: EdgeKind
    label: str


class GraphStats(BaseModel):
    total_files_found: int
    analyzed_files: int
    skipped_files: int
    skipped_reasons: dict[str, int] = Field(default_factory=dict)
    truncated: bool
    warnings: list[str] = Field(default_factory=list)


class GraphResponse(BaseModel):
    root_path: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
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
