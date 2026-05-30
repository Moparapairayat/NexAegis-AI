from pathlib import Path

from nexaegis.core.config import RiskWeights
from nexaegis.scanners.risk import analyze_risk


def test_risk_increases_when_tests_are_missing(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    result = analyze_risk(tmp_path)

    assert result.score >= 20
    assert any("No tests" in reason for reason in result.reasons)


def test_risk_low_for_complete_non_git_project_has_clear_reason(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / ".env.example").write_text("API_KEY=\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")

    result = analyze_risk(tmp_path)

    assert "Git repository" not in "\n".join(result.recommendations)
    assert any("not a Git repository" in reason for reason in result.reasons)


def test_risk_uses_configurable_weights(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    result = analyze_risk(tmp_path, weights=RiskWeights(missing_tests=50))

    assert result.score >= 50
