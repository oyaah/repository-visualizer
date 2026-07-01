from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.cache import SummaryCache
from app.ai import SummaryService
from app.graph import build_graph, slice_subgraph
from app.models import AnalyzeRequest, GraphResponse, SubgraphRequest, SummaryRequest, SummaryResponse

app = FastAPI(title="Repository Visualizer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

summary_cache = SummaryCache()
summary_service = SummaryService(summary_cache)
graph_cache: dict[tuple[str, int, bool, bool], GraphResponse] = {}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=GraphResponse)
def analyze(request: AnalyzeRequest) -> GraphResponse:
    root = Path(request.root_path)
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail="root_path must be an existing directory")
    graph = build_graph(root, request)
    graph_cache[graph_cache_key(root, request)] = graph
    return graph


@app.post("/api/subgraph", response_model=GraphResponse)
def subgraph(request: SubgraphRequest) -> GraphResponse:
    root = Path(request.root_path)
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail="root_path must be an existing directory")
    try:
        key = graph_cache_key(root, request)
        graph = graph_cache.get(key)
        if graph is None:
            graph = build_graph(root, request)
            graph_cache[key] = graph
        return slice_subgraph(graph, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def graph_cache_key(root: Path, request: AnalyzeRequest) -> tuple[str, int, bool, bool]:
    return (str(root.resolve()), request.max_files, request.include_tests, request.include_vendor)


@app.post("/api/summarize", response_model=SummaryResponse)
async def summarize(request: SummaryRequest) -> SummaryResponse:
    root = Path(request.root_path)
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail="root_path must be an existing directory")
    try:
        return await summary_service.summarize(root, request.file_path, request.model, request.cache_only)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
