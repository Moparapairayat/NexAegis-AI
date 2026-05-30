from pathlib import Path

from nexaegis.scanners.project import GOOD, MISSING, scan_project


def test_project_scanner_scores_basic_python_project(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / ".env.example").write_text("API_KEY=\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)

    result = scan_project(tmp_path)
    statuses = {check.name: check.status for check in result.checks}

    assert result.score >= 70
    assert statuses["README"] == GOOD
    assert statuses["Tests"] == GOOD


def test_project_scanner_reports_missing_manifest(tmp_path: Path) -> None:
    result = scan_project(tmp_path)
    statuses = {check.name: check.status for check in result.checks}

    assert statuses["Project manifest"] == MISSING
