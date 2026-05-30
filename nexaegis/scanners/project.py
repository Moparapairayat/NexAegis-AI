from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from nexaegis.core.scoring import clamp_score

GOOD = "Good"
WARNING = "Warning"
MISSING = "Missing"


@dataclass(frozen=True)
class ProjectCheck:
    name: str
    status: str
    detail: str
    weight: int


@dataclass(frozen=True)
class ProjectScanResult:
    project_root: Path
    score: int
    checks: list[ProjectCheck]

    def to_dict(self) -> dict[str, object]:
        return {
            "project_root": str(self.project_root),
            "score": self.score,
            "checks": [asdict(check) for check in self.checks],
        }

    def status_counts(self) -> dict[str, int]:
        return {
            GOOD: sum(1 for check in self.checks if check.status == GOOD),
            WARNING: sum(1 for check in self.checks if check.status == WARNING),
            MISSING: sum(1 for check in self.checks if check.status == MISSING),
        }

    def has_good(self, name: str) -> bool:
        return any(check.name == name and check.status == GOOD for check in self.checks)


def _exists_any(root: Path, names: tuple[str, ...]) -> bool:
    return any((root / name).exists() for name in names)


def _glob_any(root: Path, patterns: tuple[str, ...]) -> bool:
    return any(next(root.glob(pattern), None) is not None for pattern in patterns)


def scan_project(project_root: Path | None = None) -> ProjectScanResult:
    root = (project_root or Path.cwd()).resolve()
    checks: list[ProjectCheck] = []

    readme = _glob_any(root, ("README", "README.*", "readme.*"))
    checks.append(
        ProjectCheck(
            "README",
            GOOD if readme else MISSING,
            "README file found." if readme else "Add a README with setup and operating guidance.",
            12,
        )
    )

    git_repo = (root / ".git").exists()
    checks.append(
        ProjectCheck(
            "Git repository",
            GOOD if git_repo else WARNING,
            "Git repository found."
            if git_repo
            else "Project is not initialized as a Git repository.",
            10,
        )
    )

    python_project = _exists_any(root, ("pyproject.toml", "requirements.txt", "setup.py"))
    node_project = (root / "package.json").exists()
    checks.append(
        ProjectCheck(
            "Project manifest",
            GOOD if python_project or node_project else MISSING,
            "Python or Node project manifest found."
            if python_project or node_project
            else "Add pyproject.toml, requirements.txt, setup.py, or package.json.",
            12,
        )
    )

    dockerfile = _exists_any(root, ("Dockerfile", "dockerfile"))
    checks.append(
        ProjectCheck(
            "Dockerfile",
            GOOD if dockerfile else WARNING,
            "Dockerfile found."
            if dockerfile
            else "No Dockerfile found; add one if container deploys are expected.",
            6,
        )
    )

    compose = _exists_any(
        root, ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
    )
    checks.append(
        ProjectCheck(
            "Docker Compose",
            GOOD if compose else WARNING,
            "Compose file found."
            if compose
            else "No compose file found; this is optional for many projects.",
            4,
        )
    )

    tests = _exists_any(root, ("tests", "test")) or _glob_any(root, ("test_*.py", "*_test.py"))
    checks.append(
        ProjectCheck(
            "Tests",
            GOOD if tests else MISSING,
            "Test directory or test files found."
            if tests
            else "Add tests for core project behavior.",
            16,
        )
    )

    env_example = _exists_any(root, (".env.example", ".env.sample", "example.env"))
    checks.append(
        ProjectCheck(
            "Environment example",
            GOOD if env_example else WARNING,
            "Environment example found."
            if env_example
            else "Add .env.example with non-secret placeholders.",
            8,
        )
    )

    workflows = (root / ".github" / "workflows").exists()
    checks.append(
        ProjectCheck(
            "GitHub Actions",
            GOOD if workflows else WARNING,
            "GitHub Actions workflow directory found."
            if workflows
            else "Add CI workflow for tests and linting.",
            10,
        )
    )

    dependency_files = _exists_any(
        root,
        (
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "uv.lock",
            "poetry.lock",
            "Pipfile",
            "package.json",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
        ),
    )
    checks.append(
        ProjectCheck(
            "Dependency files",
            GOOD if dependency_files else MISSING,
            "Dependency file found."
            if dependency_files
            else "Add a dependency manifest or lockfile.",
            10,
        )
    )

    earned = 0.0
    possible = sum(check.weight for check in checks)
    for check in checks:
        if check.status == GOOD:
            earned += check.weight
        elif check.status == WARNING:
            earned += check.weight * 0.45

    score = clamp_score((earned / possible) * 100 if possible else 0)
    return ProjectScanResult(project_root=root, score=score, checks=checks)
