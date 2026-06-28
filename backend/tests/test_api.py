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
    assert data["stats"]["analyzed_files"] == 2
    assert data["stats"]["truncated"] is False


def test_analyze_applies_scan_options(tmp_path: Path) -> None:
    for index in range(3):
        (tmp_path / f"module_{index}.py").write_text("print('ok')\n", encoding="utf-8")

    response = client.post("/api/analyze", json={"root_path": str(tmp_path), "max_files": 1})

    assert response.status_code == 200
    data = response.json()
    assert len(data["nodes"]) == 1
    assert data["stats"]["total_files_found"] == 3
    assert data["stats"]["skipped_files"] == 2
    assert data["stats"]["truncated"] is True


def test_analyze_rejects_invalid_scan_options(tmp_path: Path) -> None:
    response = client.post("/api/analyze", json={"root_path": str(tmp_path), "max_files": 0})

    assert response.status_code == 422


def test_summarize_returns_disabled_without_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    response = client.post(
        "/api/summarize",
        json={"root_path": str(tmp_path), "file_path": "main.py", "provider": "openai"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["disabled"] is True
    assert data["cached"] is False
    assert "OPENAI_API_KEY" in data["error"]
