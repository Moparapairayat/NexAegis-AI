from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from nexaegis.core.config import NexAegisConfig


@dataclass(frozen=True)
class CommandRule:
    name: str
    pattern: re.Pattern[str]
    reason: str
    safer_alternative: str | None = None
    category: str = "general"
    action: str = "confirm"
    risk_score: int = 50


BUILTIN_POLICY_PACKS: dict[str, list[dict[str, object]]] = {
    "baseline": [
        {
            "name": "recursive_delete",
            "pattern": r"\brm\s+(-[^\s]*r[^\s]*f|-rf|-fr)\b",
            "reason": "Recursive forced deletion can remove large parts of the filesystem.",
            "safer_alternative": (
                "Inspect targets first, then delete explicit files with a non-recursive command."
            ),
            "category": "filesystem",
            "action": "confirm",
            "risk_score": 90,
        },
        {
            "name": "sudo",
            "pattern": r"(^|\s)sudo(\s|$)",
            "reason": "Elevated privileges can change system-level state.",
            "safer_alternative": (
                "Run the smallest possible command without sudo, or use a project-local tool."
            ),
            "category": "privilege",
            "action": "confirm",
            "risk_score": 75,
        },
        {
            "name": "chmod_777",
            "pattern": r"\bchmod\s+777\b",
            "reason": "chmod 777 grants write access to every user.",
            "safer_alternative": "Use the narrowest permission needed, such as chmod 755 for scripts.",
            "category": "filesystem",
            "action": "confirm",
            "risk_score": 70,
        },
        {
            "name": "force_push",
            "pattern": r"\bgit\s+push\b.*\s--force(?:\s|$|-)",
            "reason": "Force pushing can overwrite collaborators' history.",
            "safer_alternative": (
                "Use --force-with-lease only after reviewing the remote branch state."
            ),
            "category": "git",
            "action": "confirm",
            "risk_score": 85,
        },
        {
            "name": "drop_database",
            "pattern": r"\bdrop\s+database\b",
            "reason": "Dropping a database destroys data.",
            "safer_alternative": "Create a backup and target a disposable development database.",
            "category": "database",
            "action": "confirm",
            "risk_score": 95,
        },
        {
            "name": "kubectl_delete",
            "pattern": r"\bkubectl\s+delete\b",
            "reason": "Deleting Kubernetes resources can interrupt running services.",
            "safer_alternative": (
                "Run kubectl get first and scope deletions to a named development resource."
            ),
            "category": "kubernetes",
            "action": "confirm",
            "risk_score": 85,
        },
        {
            "name": "terraform_destroy",
            "pattern": r"\bterraform\s+destroy\b",
            "reason": "Terraform destroy removes managed infrastructure.",
            "safer_alternative": "Run terraform plan -destroy and require a human review.",
            "category": "infrastructure",
            "action": "confirm",
            "risk_score": 95,
        },
        {
            "name": "delete_namespace",
            "pattern": r"\bdelete\s+namespace\b",
            "reason": "Deleting a namespace can remove many resources at once.",
            "safer_alternative": (
                "List namespace contents and delete only explicit development resources."
            ),
            "category": "kubernetes",
            "action": "confirm",
            "risk_score": 90,
        },
        {
            "name": "docker_system_prune",
            "pattern": r"\bdocker\s+system\s+prune\b",
            "reason": "Docker system prune can remove images, containers, and caches.",
            "safer_alternative": (
                "Use docker image prune or docker container prune for the specific cleanup target."
            ),
            "category": "docker",
            "action": "confirm",
            "risk_score": 65,
        },
    ],
    "enterprise-strict": [
        {
            "name": "plain_curl_pipe_shell",
            "pattern": r"\b(curl|wget)\b.*\|\s*(sh|bash|pwsh|powershell)\b",
            "reason": "Piping downloaded content into a shell executes unreviewed remote code.",
            "safer_alternative": "Download the script, inspect it, then run a pinned local copy.",
            "category": "supply-chain",
            "action": "confirm",
            "risk_score": 90,
        },
        {
            "name": "npm_ignore_scripts",
            "pattern": r"\bnpm\s+install\b(?!.*--ignore-scripts)",
            "reason": "npm install can execute package lifecycle scripts.",
            "safer_alternative": "Use npm install --ignore-scripts, then review required scripts.",
            "category": "supply-chain",
            "action": "confirm",
            "risk_score": 60,
        },
    ],
}


def load_command_rules(config: NexAegisConfig, project_root: Path) -> list[CommandRule]:
    rules: list[CommandRule] = []
    for pack_name in config.policy_packs:
        for raw_rule in BUILTIN_POLICY_PACKS.get(pack_name, []):
            rules.append(_build_rule(raw_rule, source=pack_name))

    for raw_path in config.custom_policy_paths:
        path = Path(raw_path)
        path = path if path.is_absolute() else project_root / path
        rules.extend(load_custom_policy_file(path))

    return rules


def load_custom_policy_file(path: Path) -> list[CommandRule]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Policy file must contain a YAML mapping: {path}")

    rules = raw.get("command_rules", [])
    if not isinstance(rules, list):
        raise ValueError(f"`command_rules` must be a list: {path}")

    return [_build_rule(rule, source=str(path)) for rule in rules if isinstance(rule, dict)]


def _build_rule(raw_rule: dict[str, Any], *, source: str) -> CommandRule:
    name = _required_string(raw_rule, "name", source)
    pattern = _required_string(raw_rule, "pattern", source)
    reason = _required_string(raw_rule, "reason", source)
    action = str(raw_rule.get("action", "confirm")).lower()
    if action not in {"allow", "confirm", "block"}:
        raise ValueError(f"Unsupported policy action `{action}` in {source}:{name}")
    return CommandRule(
        name=name,
        pattern=re.compile(pattern, re.IGNORECASE),
        reason=reason,
        safer_alternative=_optional_string(raw_rule.get("safer_alternative")),
        category=str(raw_rule.get("category", "general")),
        action=action,
        risk_score=int(raw_rule.get("risk_score", 50)),
    )


def _required_string(raw_rule: dict[str, Any], key: str, source: str) -> str:
    value = raw_rule.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Policy rule in {source} is missing required string `{key}`.")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
