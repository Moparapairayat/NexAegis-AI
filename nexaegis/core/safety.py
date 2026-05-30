from __future__ import annotations

import shlex
from dataclasses import dataclass

from nexaegis.core.policies import BUILTIN_POLICY_PACKS, CommandRule, _build_rule


@dataclass(frozen=True)
class SafetyResult:
    allowed: bool
    requires_confirmation: bool
    reason: str
    safer_alternative: str | None = None
    category: str = "general"
    risk_score: int = 0
    matched_rules: tuple[str, ...] = ()


def evaluate_command(
    command: str,
    *,
    safe_mode: bool = True,
    rules: list[CommandRule] | None = None,
) -> SafetyResult:
    normalized = " ".join(command.strip().split())
    if not normalized:
        return SafetyResult(
            allowed=False,
            requires_confirmation=False,
            reason="Empty commands are not executable.",
            category="empty",
        )

    active_rules = rules or default_command_rules()
    matches = [rule for rule in active_rules if rule.pattern.search(normalized)]
    if matches:
        block = next((rule for rule in matches if rule.action == "block"), None)
        confirm = next((rule for rule in matches if rule.action == "confirm"), None)
        strongest = max(matches, key=lambda rule: rule.risk_score)
        rule = block or confirm or strongest
        return SafetyResult(
            allowed=False if block else rule.action == "allow" or not safe_mode,
            requires_confirmation=rule.action == "confirm",
            reason=rule.reason,
            safer_alternative=rule.safer_alternative,
            category=rule.category,
            risk_score=strongest.risk_score,
            matched_rules=tuple(match.name for match in matches),
        )

    return SafetyResult(
        allowed=True,
        requires_confirmation=False,
        reason="Command is not known-dangerous.",
        category=classify_command(normalized),
    )


def default_command_rules() -> list[CommandRule]:
    return [_build_rule(rule, source="baseline") for rule in BUILTIN_POLICY_PACKS["baseline"]]


def classify_command(command: str) -> str:
    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        return "unknown"
    if not parts:
        return "general"
    executable = parts[0].lower()
    if executable in {"git"}:
        return "git"
    if executable in {"docker", "podman"}:
        return "docker"
    if executable in {"kubectl", "helm"}:
        return "kubernetes"
    if executable in {"terraform", "tofu"}:
        return "infrastructure"
    if executable in {"python", "pytest", "uv", "pip"}:
        return "python"
    if executable in {"npm", "pnpm", "yarn", "node"}:
        return "node"
    if executable in {"rm", "del", "remove-item", "copy", "cp", "move", "mv"}:
        return "filesystem"
    return "general"
