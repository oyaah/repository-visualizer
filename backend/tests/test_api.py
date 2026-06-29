from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.ai as ai
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
    assert data["folder_summaries"][0]["name"] == "root"
    assert data["folder_summaries"][0]["files"] == 2
    assert data["cycles"] == []
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
    (tmp_path / "main.py").write_text(f"print('{tmp_path.name}')\n", encoding="utf-8")
    response = client.post(
        "/api/summarize",
        json={"root_path": str(tmp_path), "file_path": "main.py"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["disabled"] is True
    assert data["cached"] is False
    assert "OPENAI_API_KEY" in data["error"]


def test_summarize_cache_only_requires_generation_without_provider_call(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    called = False

    async def fake_provider(model: str, prompt: str) -> str:
        nonlocal called
        called = True
        return "Should not be called"

    monkeypatch.setattr(ai, "call_openai", fake_provider)
    (tmp_path / "main.py").write_text(f"print('{tmp_path.name}')\n", encoding="utf-8")

    response = client.post(
        "/api/summarize",
        json={"root_path": str(tmp_path), "file_path": "main.py", "cache_only": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is False
    assert data["requires_generation"] is True
    assert data["disabled"] is False
    assert called is False


def test_summarize_cache_only_returns_cached_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    async def fake_provider(model: str, prompt: str) -> str:
        return "Cached later"

    monkeypatch.setattr(ai, "call_openai", fake_provider)
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")

    fresh = client.post(
        "/api/summarize",
        json={"root_path": str(tmp_path), "file_path": "main.py"},
    )
    assert fresh.status_code == 200

    cached = client.post(
        "/api/summarize",
        json={"root_path": str(tmp_path), "file_path": "main.py", "cache_only": True},
    )

    assert cached.status_code == 200
    data = cached.json()
    assert data["cached"] is True
    assert data["summary"] == "Cached later"


def test_summarize_prompt_requests_actionable_sections(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured_prompt = ""

    async def fake_provider(model: str, prompt: str) -> str:
        nonlocal captured_prompt
        captured_prompt = prompt
        return "- Purpose: Starts the app.\n- Key dependencies: utils.\n- Change risk: Routes may break.\n- Read next: utils.py"

    monkeypatch.setattr(ai, "call_openai", fake_provider)
    (tmp_path / "main.py").write_text(f"import utils\nRUN_ID = '{tmp_path}'\nutils.run()\n", encoding="utf-8")

    response = client.post(
        "/api/summarize",
        json={"root_path": str(tmp_path), "file_path": "main.py"},
    )

    assert response.status_code == 200
    assert "Purpose:" in captured_prompt
    assert "Key dependencies:" in captured_prompt
    assert "Change risk:" in captured_prompt
    assert "Read next:" in captured_prompt
    assert "File: main.py" in captured_prompt
