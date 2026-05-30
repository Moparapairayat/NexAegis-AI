from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from nexaegis.core.config import NexAegisConfig


class PolicyError(RuntimeError):
    """Raised when command policy configuration cannot be loaded safely."""


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
        {
            "name": "powershell_recursive_delete",
            "pattern": (
                r"\b(remove-item|rm|rmdir|rd|del|erase)\b"
                r"(?=.*\s-(recurse|r)\b)(?=.*\s-(force|fo)\b)"
            ),
            "reason": "Recursive forced deletion can remove large parts of the filesystem.",
            "safer_alternative": (
                "Inspect targets first, then delete explicit files without recursive force flags."
            ),
            "category": "filesystem",
            "action": "confirm",
            "risk_score": 90,
        },
        {
            "name": "cmd_recursive_delete",
            "pattern": r"\b(rmdir|rd|del|erase)\b(?=.*\s/s\b)(?=.*\s/q\b)",
            "reason": "Recursive quiet deletion can remove many files without review.",
            "safer_alternative": (
                "List the target path first and delete a specific reviewed file or directory."
            ),
            "category": "filesystem",
            "action": "confirm",
            "risk_score": 85,
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
        raw_rules = BUILTIN_POLICY_PACKS.get(pack_name)
        if raw_rules is None:
            known = ", ".join(sorted(BUILTIN_POLICY_PACKS))
            raise PolicyError(f"Unknown policy pack `{pack_name}`. Known packs: {known}.")
        for raw_rule in raw_rules:
            rules.append(_build_rule(raw_rule, source=pack_name))

    for raw_path in config.custom_policy_paths:
        path = Path(raw_path)
        path = path if path.is_absolute() else project_root / path
        rules.extend(load_custom_policy_file(path))

    return rules


def load_custom_policy_file(path: Path) -> list[CommandRule]:
    if not path.exists():
        raise PolicyError(f"Policy file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PolicyError(f"Could not parse policy file {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PolicyError(f"Policy file must contain a YAML mapping: {path}")

    rules = raw.get("command_rules", [])
    if not isinstance(rules, list):
        raise PolicyError(f"`command_rules` must be a list: {path}")

    built_rules: list[CommandRule] = []
    for index, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            raise PolicyError(f"Policy rule #{index} in {path} must be a mapping.")
        built_rules.append(_build_rule(rule, source=str(path)))
    return built_rules


def _build_rule(raw_rule: dict[str, Any], *, source: str) -> CommandRule:
    name = _required_string(raw_rule, "name", source)
    pattern = _required_string(raw_rule, "pattern", source)
    reason = _required_string(raw_rule, "reason", source)
    action = str(raw_rule.get("action", "confirm")).lower()
    if action not in {"allow", "confirm", "block"}:
        raise PolicyError(f"Unsupported policy action `{action}` in {source}:{name}")
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise PolicyError(f"Invalid regex in policy rule {source}:{name}: {exc}") from exc
    return CommandRule(
        name=name,
        pattern=compiled,
        reason=reason,
        safer_alternative=_optional_string(raw_rule.get("safer_alternative")),
        category=str(raw_rule.get("category", "general")),
        action=action,
        risk_score=_risk_score(raw_rule.get("risk_score", 50), source=source, name=name),
    )


def _required_string(raw_rule: dict[str, Any], key: str, source: str) -> str:
    value = raw_rule.get(key)
    if not isinstance(value, str) or not value:
        raise PolicyError(f"Policy rule in {source} is missing required string `{key}`.")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _risk_score(value: object, *, source: str, name: str) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError) as exc:
        raise PolicyError(f"Invalid risk_score in policy rule {source}:{name}") from exc
    return max(0, min(100, score))
