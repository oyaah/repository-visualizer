from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.cache import SummaryCache
from app.ai import SummaryService
from app.graph import build_graph
from app.models import AnalyzeRequest, GraphResponse, SummaryRequest, SummaryResponse

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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=GraphResponse)
def analyze(request: AnalyzeRequest) -> GraphResponse:
    root = Path(request.root_path)
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail="root_path must be an existing directory")
    return build_graph(root)


@app.post("/api/summarize", response_model=SummaryResponse)
async def summarize(request: SummaryRequest) -> SummaryResponse:
    root = Path(request.root_path)
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail="root_path must be an existing directory")
    try:
        return await summary_service.summarize(root, request.file_path, request.provider, request.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

