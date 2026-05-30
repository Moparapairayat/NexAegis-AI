from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from nexaegis.core.config import RiskWeights
from nexaegis.core.scoring import clamp_score, risk_level
from nexaegis.scanners.git import changed_files, is_git_repo
from nexaegis.scanners.project import scan_project

SENSITIVE_TERMS = (
    "auth",
    "payment",
    "billing",
    "user",
    "account",
    "session",
    "migration",
    "database",
    "settings",
    "config",
    "deploy",
    "docker",
    "k8s",
    "terraform",
)

DEPENDENCY_FILES = (
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "uv.lock",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
)


@dataclass(frozen=True)
class RiskResult:
    project_root: Path
    score: int
    level: str
    changed_files: list[str]
    reasons: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["project_root"] = str(self.project_root)
        return payload


def analyze_risk(
    project_root: Path | None = None, weights: RiskWeights | None = None
) -> RiskResult:
    root = (project_root or Path.cwd()).resolve()
    risk_weights = weights or RiskWeights()
    scan = scan_project(root)
    changes = changed_files(root)
    reasons: list[str] = []
    recommendations: list[str] = []
    score = 0

    if not is_git_repo(root):
        score += risk_weights.not_git_repo
        reasons.append(
            "Project is not a Git repository, so change risk cannot be fully attributed."
        )
        recommendations.append("Initialize Git and review changes before release.")
    elif changes:
        score += risk_weights.changed_file_base + min(
            risk_weights.changed_file_cap,
            risk_weights.changed_file_per_file * len(changes),
        )
        reasons.append(f"{len(changes)} changed file(s) in the working tree.")
        recommendations.append(
            "Review and test the current diff before applying fixes or committing."
        )

    sensitive_changes = [
        file for file in changes if any(term in file.lower() for term in SENSITIVE_TERMS)
    ]
    if sensitive_changes:
        score += min(
            risk_weights.sensitive_cap,
            risk_weights.sensitive_base
            + (risk_weights.sensitive_per_file * len(sensitive_changes)),
        )
        reasons.append("Sensitive-area changes detected: " + ", ".join(sensitive_changes[:5]))
        recommendations.append(
            "Require focused review for auth, config, data, deployment, or billing changes."
        )

    dependency_changes = [
        file
        for file in changes
        if Path(file).name.lower() in {name.lower() for name in DEPENDENCY_FILES}
    ]
    if dependency_changes:
        score += risk_weights.dependency_change
        reasons.append("Dependency manifest or lockfile changed.")
        recommendations.append("Run dependency audit and lockfile verification.")

    if not scan.has_good("Tests"):
        score += risk_weights.missing_tests
        reasons.append("No tests were detected.")
        recommendations.append("Add at least smoke tests before making risky changes.")

    if not scan.has_good("GitHub Actions"):
        score += risk_weights.missing_ci
        reasons.append("No GitHub Actions CI workflow was detected.")
        recommendations.append("Add CI for tests and lint checks.")

    if not scan.has_good("Dockerfile"):
        score += risk_weights.missing_dockerfile
        reasons.append("No Dockerfile was detected.")
        recommendations.append("Add a Dockerfile if production deploys depend on containers.")

    if not scan.has_good("Environment example"):
        score += risk_weights.missing_env_example
        reasons.append("No .env.example file was detected.")
        recommendations.append("Document required environment variables with safe placeholders.")

    if not reasons:
        reasons.append("No major project or change risk signals detected.")
        recommendations.append("Keep tests and CI passing before release.")

    final_score = clamp_score(score)
    return RiskResult(
        project_root=root,
        score=final_score,
        level=risk_level(final_score),
        changed_files=changes,
        reasons=reasons,
        recommendations=recommendations,
    )
