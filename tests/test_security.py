from pathlib import Path

from nexaegis.scanners.security import scan_security


def test_security_scan_does_not_crash_when_optional_tools_missing(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")

    result = scan_security(tmp_path)

    assert 0 <= result.score <= 100
    assert {tool.name for tool in result.tools} == {
        "bandit",
        "pip-audit",
        "detect-secrets",
        "gitleaks",
    }


def test_security_scan_warns_when_gitignore_missing_env(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")

    result = scan_security(tmp_path)

    assert any(".gitignore" in (finding.path or "") for finding in result.findings)


def test_security_scan_detects_iac_risks(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:latest\n", encoding="utf-8")
    (tmp_path / "main.tf").write_text(
        'cidr_blocks = ["0.0.0.0/0"]\npublicly_accessible = true\n',
        encoding="utf-8",
    )
    (tmp_path / "deployment.yaml").write_text(
        "securityContext:\n  privileged: true\n",
        encoding="utf-8",
    )

    result = scan_security(tmp_path)
    titles = {finding.title for finding in result.findings}

    assert "Docker image uses the latest tag" in titles
    assert "Terraform enables public accessibility" in titles
    assert "Kubernetes workload enables privileged mode" in titles


def test_security_scan_ignores_local_state_directories(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    ignored = tmp_path / ".nexaegis" / "backups"
    ignored.mkdir(parents=True)
    (ignored / "secret-token.key").write_text("not printed\n", encoding="utf-8")

    result = scan_security(tmp_path)

    assert not any(finding.path == ".nexaegis/backups/secret-token.key" for finding in result.findings)
