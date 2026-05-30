from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from nexaegis.core.scoring import clamp_score


@dataclass(frozen=True)
class SecurityToolResult:
    name: str
    installed: bool
    status: str
    suggestion: str
    finding_count: int = 0


@dataclass(frozen=True)
class SecurityFinding:
    severity: str
    title: str
    path: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class SecurityResult:
    project_root: Path
    score: int
    tools: list[SecurityToolResult]
    findings: list[SecurityFinding]

    def to_dict(self) -> dict[str, object]:
        return {
            "project_root": str(self.project_root),
            "score": self.score,
            "tools": [asdict(tool) for tool in self.tools],
            "findings": [asdict(finding) for finding in self.findings],
        }


TOOLS: dict[str, tuple[list[str], str]] = {
    "bandit": (
        ["bandit", "-r", ".", "-q", "-f", "json"],
        "Install with: uv add --dev bandit",
    ),
    "pip-audit": (
        ["pip-audit", "-f", "json"],
        "Install with: uv add --dev pip-audit",
    ),
    "detect-secrets": (
        ["detect-secrets", "scan", "--all-files"],
        "Install with: uv add --dev detect-secrets",
    ),
    "gitleaks": (
        ["gitleaks", "detect", "--source", ".", "--no-git", "--redact", "--report-format", "json"],
        "Install from https://github.com/gitleaks/gitleaks",
    ),
}

SECRET_FILE_TERMS = (
    "secret",
    "credential",
    "credentials",
    "token",
    "private_key",
    "id_rsa",
)


def scan_security(project_root: Path | None = None) -> SecurityResult:
    root = (project_root or Path.cwd()).resolve()
    tools = [
        _run_tool(root, name, command, suggestion) for name, (command, suggestion) in TOOLS.items()
    ]
    findings = _builtin_findings(root)

    tool_finding_count = sum(tool.finding_count for tool in tools)
    high = sum(1 for finding in findings if finding.severity.lower() == "high")
    medium = sum(1 for finding in findings if finding.severity.lower() == "medium")
    low = sum(1 for finding in findings if finding.severity.lower() == "low")
    score = clamp_score(
        100 - (high * 25) - (medium * 12) - (low * 5) - min(35, tool_finding_count * 5)
    )
    return SecurityResult(project_root=root, score=score, tools=tools, findings=findings)


def _run_tool(root: Path, name: str, command: list[str], suggestion: str) -> SecurityToolResult:
    executable = shutil.which(command[0])
    if executable is None:
        return SecurityToolResult(
            name=name,
            installed=False,
            status="not installed",
            suggestion=suggestion,
        )

    try:
        result = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SecurityToolResult(
            name=name,
            installed=True,
            status=f"error: {exc}",
            suggestion="Review the scanner output and retry.",
        )

    finding_count = _estimate_finding_count(name, result.stdout, result.stderr)
    status = "passed" if result.returncode == 0 and finding_count == 0 else "findings or warnings"
    return SecurityToolResult(
        name=name,
        installed=True,
        status=status,
        suggestion="Review scanner output." if finding_count else "No action needed.",
        finding_count=finding_count,
    )


def _estimate_finding_count(name: str, stdout: str, stderr: str) -> int:
    content = stdout.strip() or stderr.strip()
    if not content:
        return 0
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return 1

    if name == "bandit":
        return len(data.get("results", [])) if isinstance(data, dict) else 0
    if name == "pip-audit":
        if isinstance(data, list):
            return sum(len(item.get("vulns", [])) for item in data if isinstance(item, dict))
        if isinstance(data, dict):
            dependencies = data.get("dependencies", [])
            if isinstance(dependencies, list):
                return sum(
                    len(item.get("vulns", [])) for item in dependencies if isinstance(item, dict)
                )
    if name == "gitleaks":
        return len(data) if isinstance(data, list) else 0
    if name == "detect-secrets" and isinstance(data, dict):
        results = data.get("results", {})
        return sum(len(value) for value in results.values()) if isinstance(results, dict) else 0
    return 1


def _builtin_findings(root: Path) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []

    env_file = root / ".env"
    if env_file.exists():
        tracked = _is_git_tracked(root, ".env")
        findings.append(
            SecurityFinding(
                severity="high" if tracked else "medium",
                title=".env file is present" + (" and tracked by Git" if tracked else ""),
                path=".env",
                detail="Do not commit secret-bearing environment files.",
            )
        )

    gitignore = root / ".gitignore"
    if gitignore.exists():
        ignores_env = any(
            line.strip() == ".env" for line in gitignore.read_text(encoding="utf-8").splitlines()
        )
        if not ignores_env:
            findings.append(
                SecurityFinding(
                    severity="medium",
                    title=".gitignore does not explicitly ignore .env",
                    path=".gitignore",
                    detail="Add .env to reduce accidental secret commits.",
                )
            )
    else:
        findings.append(
            SecurityFinding(
                severity="medium",
                title=".gitignore is missing",
                detail="Add .gitignore and ignore .env files.",
            )
        )

    for path in root.rglob("*"):
        if not path.is_file() or _is_ignored_path(path, root):
            continue
        relative = path.relative_to(root).as_posix()
        lowered = path.name.lower()
        if lowered.endswith((".pem", ".key")) or any(term in lowered for term in SECRET_FILE_TERMS):
            findings.append(
                SecurityFinding(
                    severity="medium",
                    title="Secret-like filename detected",
                    path=relative,
                    detail="Review the file without printing secret values.",
                )
            )
        findings.extend(_iac_findings(path, root))

    return findings


def _iac_findings(path: Path, root: Path) -> list[SecurityFinding]:
    relative = path.relative_to(root).as_posix()
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name in {"dockerfile", "containerfile"} or name.startswith("dockerfile."):
        return _dockerfile_findings(path, relative)
    if suffix == ".tf":
        return _terraform_findings(path, relative)
    if suffix in {".yaml", ".yml"}:
        return _kubernetes_findings(path, relative)
    return []


def _dockerfile_findings(path: Path, relative: str) -> list[SecurityFinding]:
    text = _read_lower(path)
    findings: list[SecurityFinding] = []
    if "from " in text and ":latest" in text:
        findings.append(
            SecurityFinding(
                severity="medium",
                title="Docker image uses the latest tag",
                path=relative,
                detail="Pin base images to an explicit version or digest.",
            )
        )
    if "user " not in text:
        findings.append(
            SecurityFinding(
                severity="low",
                title="Dockerfile does not set a non-root USER",
                path=relative,
                detail="Run containers as a non-root user where possible.",
            )
        )
    if "add http://" in text or "add https://" in text:
        findings.append(
            SecurityFinding(
                severity="medium",
                title="Dockerfile downloads remote content with ADD",
                path=relative,
                detail="Prefer verified downloads with checksums in a controlled build step.",
            )
        )
    return findings


def _terraform_findings(path: Path, relative: str) -> list[SecurityFinding]:
    text = _read_lower(path)
    findings: list[SecurityFinding] = []
    if "0.0.0.0/0" in text:
        findings.append(
            SecurityFinding(
                severity="medium",
                title="Terraform allows traffic from 0.0.0.0/0",
                path=relative,
                detail="Restrict ingress CIDR blocks to trusted networks.",
            )
        )
    if "publicly_accessible" in text and "true" in text:
        findings.append(
            SecurityFinding(
                severity="high",
                title="Terraform enables public accessibility",
                path=relative,
                detail="Confirm public exposure is intentional and protected.",
            )
        )
    return findings


def _kubernetes_findings(path: Path, relative: str) -> list[SecurityFinding]:
    text = _read_lower(path)
    findings: list[SecurityFinding] = []
    if "privileged: true" in text:
        findings.append(
            SecurityFinding(
                severity="high",
                title="Kubernetes workload enables privileged mode",
                path=relative,
                detail="Avoid privileged containers unless a reviewed exception exists.",
            )
        )
    if "hostnetwork: true" in text:
        findings.append(
            SecurityFinding(
                severity="high",
                title="Kubernetes workload enables hostNetwork",
                path=relative,
                detail="hostNetwork increases blast radius and should be exceptional.",
            )
        )
    if "runasuser: 0" in text:
        findings.append(
            SecurityFinding(
                severity="medium",
                title="Kubernetes workload runs as root",
                path=relative,
                detail="Set a non-root runAsUser where possible.",
            )
        )
    if "image:" in text and ":latest" in text:
        findings.append(
            SecurityFinding(
                severity="low",
                title="Kubernetes image uses latest tag",
                path=relative,
                detail="Pin container images to explicit versions or digests.",
            )
        )
    return findings


def _read_lower(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lower()


def _is_git_tracked(root: Path, relative_path: str) -> bool:
    if not (root / ".git").exists():
        return False
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", relative_path],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _is_ignored_path(path: Path, root: Path) -> bool:
    parts = set(path.relative_to(root).parts)
    return bool(
        parts
        & {
            ".git",
            ".nexaegis",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
        }
    )
