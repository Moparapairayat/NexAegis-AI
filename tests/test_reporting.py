from pathlib import Path

from nexaegis.core.config import default_config
from nexaegis.core.reporting import (
    build_project_report,
    report_to_json,
    report_to_markdown,
    report_to_sarif,
)


def test_report_renders_json_and_markdown(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")

    report = build_project_report(tmp_path, default_config(tmp_path))

    assert '"doctor"' in report_to_json(report)
    assert "# NexAegis AI Report" in report_to_markdown(report)
    assert '"version": "2.1.0"' in report_to_sarif(report)
