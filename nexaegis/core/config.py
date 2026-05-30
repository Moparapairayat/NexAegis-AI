from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

STATE_DIR = ".nexaegis"
CONFIG_FILE = "config.yaml"
DB_FILE = "nexaegis.db"


class RiskWeights(BaseModel):
    not_git_repo: int = 18
    changed_file_base: int = 0
    changed_file_per_file: int = 3
    changed_file_cap: int = 18
    sensitive_base: int = 12
    sensitive_per_file: int = 4
    sensitive_cap: int = 30
    dependency_change: int = 15
    missing_tests: int = 20
    missing_ci: int = 10
    missing_dockerfile: int = 5
    missing_env_example: int = 10


class NexAegisConfig(BaseModel):
    project_name: str
    safe_mode: bool = True
    ai_provider: str = "rule_based"
    ollama_model: str = "qwen2.5-coder:1.5b"
    risk_threshold: str = "medium"
    allow_apply_patch: bool = True
    allow_command_execution: bool = False
    ci_min_health_score: int = 70
    ci_min_security_score: int = 80
    ci_max_risk_level: str = "medium"
    risk_weights: RiskWeights = RiskWeights()


class ConfigError(RuntimeError):
    """Raised when project config cannot be parsed or validated."""


def project_name_from_path(project_root: Path) -> str:
    return project_root.resolve().name or "project"


def default_config(project_root: Path) -> NexAegisConfig:
    return NexAegisConfig(project_name=project_name_from_path(project_root))


def state_dir(project_root: Path) -> Path:
    return project_root / STATE_DIR


def config_path(project_root: Path) -> Path:
    return state_dir(project_root) / CONFIG_FILE


def db_path(project_root: Path) -> Path:
    return state_dir(project_root) / DB_FILE


def backups_dir(project_root: Path) -> Path:
    return state_dir(project_root) / "backups"


def ensure_state_dir(project_root: Path) -> Path:
    path = state_dir(project_root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_to_yaml(config: NexAegisConfig) -> str:
    return yaml.safe_dump(config.model_dump(), sort_keys=False)


def write_default_config(project_root: Path, *, overwrite: bool = False) -> Path:
    ensure_state_dir(project_root)
    path = config_path(project_root)
    if path.exists() and not overwrite:
        return path
    path.write_text(config_to_yaml(default_config(project_root)), encoding="utf-8")
    return path


def load_config(project_root: Path | None = None) -> NexAegisConfig:
    root = (project_root or Path.cwd()).resolve()
    path = config_path(root)
    if not path.exists():
        return default_config(root)

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a YAML mapping.")

    merged: dict[str, Any] = default_config(root).model_dump()
    merged.update(raw)
    try:
        return NexAegisConfig.model_validate(merged)
    except ValidationError as exc:
        raise ConfigError(f"Invalid NexAegis config in {path}: {exc}") from exc
