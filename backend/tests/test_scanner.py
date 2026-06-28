from __future__ import annotations

from pathlib import Path

from app.scanner import calculate_metrics, scan_repository


def test_scan_ignores_noisy_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("import x from 'x'\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("ignored", encoding="utf-8")

    files, ignored = scan_repository(tmp_path)

    assert [file.relative_path for file in files] == ["src/app.py"]
    assert "node_modules" in ignored


def test_metrics_count_loc_and_complexity() -> None:
    metrics = calculate_metrics("if value:\n    return value\n\nreturn None\n", 42)
    assert metrics.loc == 3
    assert metrics.total_lines == 4
    assert metrics.size_bytes == 42
    assert metrics.complexity > 1

