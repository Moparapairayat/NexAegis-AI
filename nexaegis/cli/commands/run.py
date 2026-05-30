from __future__ import annotations

import subprocess
from dataclasses import asdict
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from nexaegis.core.context import ProjectContext, get_project_context
from nexaegis.core.policies import PolicyError, load_command_rules
from nexaegis.core.safety import SafetyResult, evaluate_command

console = Console()


def run_command(
    command: Annotated[str, typer.Argument(help="Command string to inspect and optionally run.")],
    execute: Annotated[
        bool,
        typer.Option(
            "--execute",
            help="Run this explicit command even when allow_command_execution is false.",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation for non-dangerous commands."),
    ] = False,
    confirm_danger: Annotated[
        bool,
        typer.Option(
            "--confirm-danger",
            help="Acknowledge a dangerous command. Still requires confirmation unless --yes is also set.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Only show the safety verdict; do not execute."),
    ] = False,
    timeout: Annotated[int, typer.Option("--timeout", help="Execution timeout in seconds.")] = 120,
) -> None:
    """Risk-check a command before execution."""
    context = get_project_context()
    run_checked_command(
        context,
        command,
        execute=execute,
        yes=yes,
        confirm_danger=confirm_danger,
        dry_run=dry_run,
        timeout=timeout,
    )


def run_checked_command(
    context: ProjectContext,
    command: str,
    *,
    execute: bool = False,
    yes: bool = False,
    confirm_danger: bool = False,
    dry_run: bool = False,
    timeout: int = 120,
) -> int | None:
    try:
        rules = load_command_rules(context.config, context.root)
    except PolicyError as exc:
        safety = SafetyResult(
            allowed=False,
            requires_confirmation=False,
            reason=f"Policy configuration error: {exc}",
            safer_alternative="Fix the policy configuration before running commands.",
            category="policy",
            risk_score=100,
            matched_rules=("policy_error",),
        )
        _print_safety_panel(command, safety)
        record = asdict(safety) | {
            "dry_run": dry_run,
            "execute_requested": execute,
            "status": "blocked_by_policy_error",
        }
        context.store.record_command(command, record)
        raise typer.Exit(code=2)

    safety = evaluate_command(command, safe_mode=context.config.safe_mode, rules=rules)
    _print_safety_panel(command, safety)

    record = asdict(safety) | {"dry_run": dry_run, "execute_requested": execute}
    if dry_run:
        record["status"] = "dry_run"
        context.store.record_command(command, record)
        return None

    if not safety.allowed and not safety.requires_confirmation:
        record["status"] = "blocked_by_policy"
        context.store.record_command(command, record)
        console.print("[red]Command blocked by policy and cannot be overridden.[/red]")
        raise typer.Exit(code=1)

    if not context.config.allow_command_execution and not execute:
        record["status"] = "blocked_by_config"
        context.store.record_command(command, record)
        console.print(
            "[yellow]Command execution is disabled by config. Re-run with --execute for this "
            "explicit command after review.[/yellow]"
        )
        return None

    if safety.requires_confirmation:
        if not confirm_danger and context.config.safe_mode:
            if not Confirm.ask(
                "This command is dangerous. Do you explicitly approve it?", default=False
            ):
                record["status"] = "danger_not_approved"
                context.store.record_command(command, record)
                console.print("Aborted. Command was not run.")
                return None
        elif (
            confirm_danger
            and not yes
            and not Confirm.ask(
                "Danger acknowledged. Run the command now?",
                default=False,
            )
        ):
            record["status"] = "danger_acknowledged_but_aborted"
            context.store.record_command(command, record)
            console.print("Aborted. Command was not run.")
            return None
    elif not yes and not Confirm.ask("Run this command?", default=False):
        record["status"] = "aborted"
        context.store.record_command(command, record)
        console.print("Aborted. Command was not run.")
        return None

    try:
        result = subprocess.run(
            command,
            cwd=context.root,
            shell=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        record["status"] = "timeout"
        record["timeout"] = timeout
        context.store.record_command(command, record)
        console.print(f"[red]Command timed out after {timeout} seconds.[/red]")
        raise typer.Exit(code=124) from None

    record["status"] = "executed"
    record["returncode"] = result.returncode
    context.store.record_command(command, record)
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)
    return result.returncode


def _print_safety_panel(command: str, safety: SafetyResult) -> None:
    color = "red" if safety.requires_confirmation or not safety.allowed else "green"
    console.print(
        Panel.fit(
            "\n".join(
                [
                    f"Command: {command}",
                    f"Category: {safety.category}",
                    f"Risk score: {safety.risk_score}/100",
                    f"Matched rules: {', '.join(safety.matched_rules) or 'none'}",
                    f"Allowed by policy: {safety.allowed}",
                    f"Requires confirmation: {safety.requires_confirmation}",
                    f"Reason: {safety.reason}",
                    f"Safer alternative: {safety.safer_alternative or 'n/a'}",
                ]
            ),
            title="NexAegis Command Firewall",
            border_style=color,
        )
    )
