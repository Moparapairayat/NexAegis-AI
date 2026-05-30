from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from nexaegis.core.safety import SafetyResult, evaluate_command


@dataclass(frozen=True)
class ExecutionResult:
    command: str
    safety: SafetyResult
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""


def run_guarded_command(
    command: list[str],
    *,
    cwd: Path,
    safe_mode: bool = True,
    allow_execution: bool = False,
    timeout: int = 120,
) -> ExecutionResult:
    display = " ".join(command)
    safety = evaluate_command(display, safe_mode=safe_mode)
    if not allow_execution or not safety.allowed:
        return ExecutionResult(command=display, safety=safety)

    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return ExecutionResult(
        command=display,
        safety=safety,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
