from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_rejects_missing_root() -> None:
    response = client.post("/api/analyze", json={"root_path": "/definitely/missing/path"})
    assert response.status_code == 400


def test_analyze_returns_graph_for_fixture(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("from . import utils\n", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    response = client.post("/api/analyze", json={"root_path": str(tmp_path)})
    assert response.status_code == 200
    data = response.json()
    assert len(data["nodes"]) == 2
    assert data["edges"][0]["source"] == "main.py"
    assert data["edges"][0]["target"] == "utils.py"

