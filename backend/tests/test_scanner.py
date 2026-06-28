from __future__ import annotations

from pathlib import Path

from app.models import AnalyzeRequest
from app.scanner import calculate_metrics, scan_repository


def test_scan_ignores_noisy_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("import x from 'x'\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("ignored", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert [file.relative_path for file in result.files] == ["src/app.py"]
    assert "node_modules" in result.ignored_directories


def test_scan_policy_excludes_tests_and_vendor_like_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("import src.app\n", encoding="utf-8")
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "lib.js").write_text("export const x = 1\n", encoding="utf-8")
    (tmp_path / "src" / "bundle.min.js").write_text("var x=1;\n", encoding="utf-8")

    result = scan_repository(tmp_path, AnalyzeRequest(root_path=str(tmp_path), include_tests=False))

    assert [file.relative_path for file in result.files] == ["src/app.py"]
    assert result.skipped_files == 1
    assert result.skipped_reasons == {"scan_policy": 1}
    assert "tests" in result.ignored_directories
    assert "vendor" in result.ignored_directories


def test_scan_applies_root_gitignore_patterns(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("fixtures/\n*.snap.ts\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "src" / "view.snap.ts").write_text("export const x = 1\n", encoding="utf-8")
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "seed.py").write_text("print('skip')\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert [file.relative_path for file in result.files] == ["src/app.py"]
    assert result.skipped_reasons == {"gitignore": 1}
    assert "fixtures" in result.ignored_directories


def test_scan_honors_gitignore_negation_for_files(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*.ts\n!keep.ts\n", encoding="utf-8")
    (tmp_path / "skip.ts").write_text("export const skip = true;\n", encoding="utf-8")
    (tmp_path / "keep.ts").write_text("export const keep = true;\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert [file.relative_path for file in result.files] == ["keep.ts"]
    assert result.skipped_reasons == {"gitignore": 1}


def test_scan_policy_caps_analyzed_files(tmp_path: Path) -> None:
    for index in range(3):
        (tmp_path / f"module_{index}.py").write_text("print('ok')\n", encoding="utf-8")

    result = scan_repository(tmp_path, AnalyzeRequest(root_path=str(tmp_path), max_files=2))

    assert [file.relative_path for file in result.files] == ["module_0.py", "module_1.py"]
    assert result.total_files_found == 3
    assert result.skipped_files == 1
    assert result.skipped_reasons == {"max_files": 1}
    assert result.truncated is True
    assert result.warnings


def test_metrics_count_loc_and_complexity() -> None:
    metrics = calculate_metrics("if value:\n    return value\n\nreturn None\n", 42)
    assert metrics.loc == 3
    assert metrics.total_lines == 4
    assert metrics.size_bytes == 42
    assert metrics.complexity > 1
