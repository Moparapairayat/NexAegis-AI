from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyResult:
    allowed: bool
    requires_confirmation: bool
    reason: str
    safer_alternative: str | None = None


@dataclass(frozen=True)
class DangerousPattern:
    name: str
    pattern: re.Pattern[str]
    reason: str
    safer_alternative: str | None = None


DANGEROUS_PATTERNS: tuple[DangerousPattern, ...] = (
    DangerousPattern(
        name="recursive_delete",
        pattern=re.compile(r"\brm\s+(-[^\s]*r[^\s]*f|-rf|-fr)\b", re.IGNORECASE),
        reason="Recursive forced deletion can remove large parts of the filesystem.",
        safer_alternative="Inspect targets first, then delete explicit files with a non-recursive command.",
    ),
    DangerousPattern(
        name="sudo",
        pattern=re.compile(r"(^|\s)sudo(\s|$)", re.IGNORECASE),
        reason="Elevated privileges can change system-level state.",
        safer_alternative="Run the smallest possible command without sudo, or use a project-local tool.",
    ),
    DangerousPattern(
        name="chmod_777",
        pattern=re.compile(r"\bchmod\s+777\b", re.IGNORECASE),
        reason="chmod 777 grants write access to every user.",
        safer_alternative="Use the narrowest permission needed, such as chmod 755 for scripts.",
    ),
    DangerousPattern(
        name="force_push",
        pattern=re.compile(r"\bgit\s+push\b.*\s--force(?:\s|$|-)", re.IGNORECASE),
        reason="Force pushing can overwrite collaborators' history.",
        safer_alternative="Use --force-with-lease only after reviewing the remote branch state.",
    ),
    DangerousPattern(
        name="drop_database",
        pattern=re.compile(r"\bdrop\s+database\b", re.IGNORECASE),
        reason="Dropping a database destroys data.",
        safer_alternative="Create a backup and target a disposable development database.",
    ),
    DangerousPattern(
        name="kubectl_delete",
        pattern=re.compile(r"\bkubectl\s+delete\b", re.IGNORECASE),
        reason="Deleting Kubernetes resources can interrupt running services.",
        safer_alternative="Run kubectl get first and scope deletions to a named development resource.",
    ),
    DangerousPattern(
        name="terraform_destroy",
        pattern=re.compile(r"\bterraform\s+destroy\b", re.IGNORECASE),
        reason="Terraform destroy removes managed infrastructure.",
        safer_alternative="Run terraform plan -destroy and require a human review.",
    ),
    DangerousPattern(
        name="delete_namespace",
        pattern=re.compile(r"\bdelete\s+namespace\b", re.IGNORECASE),
        reason="Deleting a namespace can remove many resources at once.",
        safer_alternative="List namespace contents and delete only explicit development resources.",
    ),
    DangerousPattern(
        name="docker_system_prune",
        pattern=re.compile(r"\bdocker\s+system\s+prune\b", re.IGNORECASE),
        reason="Docker system prune can remove images, containers, and caches.",
        safer_alternative="Use docker image prune or docker container prune for the specific cleanup target.",
    ),
)


def evaluate_command(command: str, *, safe_mode: bool = True) -> SafetyResult:
    normalized = " ".join(command.strip().split())
    if not normalized:
        return SafetyResult(
            allowed=False,
            requires_confirmation=False,
            reason="Empty commands are not executable.",
        )

    for dangerous in DANGEROUS_PATTERNS:
        if dangerous.pattern.search(normalized):
            return SafetyResult(
                allowed=not safe_mode,
                requires_confirmation=True,
                reason=dangerous.reason,
                safer_alternative=dangerous.safer_alternative,
            )

    return SafetyResult(
        allowed=True, requires_confirmation=False, reason="Command is not known-dangerous."
    )
