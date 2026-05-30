from pathlib import Path

from nexaegis.core.config import config_path, load_config, write_default_config


def test_default_config_uses_project_name(tmp_path: Path) -> None:
    config = load_config(tmp_path)

    assert config.project_name == tmp_path.name
    assert config.safe_mode is True
    assert config.ai_provider == "rule_based"
    assert config.allow_command_execution is False
    assert config.ci_min_health_score == 70
    assert config.risk_weights.missing_tests == 20


def test_write_default_config_creates_yaml(tmp_path: Path) -> None:
    path = write_default_config(tmp_path)

    assert path == config_path(tmp_path)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "safe_mode: true" in text
    assert "risk_weights:" in text
