from __future__ import annotations

import subprocess
from pathlib import Path

IGNORED_STATUS_PREFIXES = (".nexaegis/", ".nexaegis\\")


def is_git_repo(project_root: Path) -> bool:
    return (project_root / ".git").exists() or _git(
        project_root, ["rev-parse", "--is-inside-work-tree"]
    ).returncode == 0


def changed_files(project_root: Path) -> list[str]:
    if not is_git_repo(project_root):
        return []
    result = _git(project_root, ["status", "--porcelain"])
    files: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path.startswith(IGNORED_STATUS_PREFIXES):
            continue
        files.append(path)
    return files


def status_summary(project_root: Path) -> str:
    if not is_git_repo(project_root):
        return "Not a Git repository"
    files = changed_files(project_root)
    if not files:
        return "Clean working tree"
    return f"{len(files)} changed file(s)"


def diff_stat(project_root: Path) -> str:
    if not is_git_repo(project_root):
        return ""
    result = _git(project_root, ["diff", "--stat"])
    staged = _git(project_root, ["diff", "--cached", "--stat"])
    lines = [line for line in (result.stdout + staged.stdout).splitlines() if line.strip()]
    return "\n".join(lines)


def _git(project_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(project_root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
