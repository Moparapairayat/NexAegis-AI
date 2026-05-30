from __future__ import annotations

import subprocess
from dataclasses import asdict
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from nexaegis.core.context import get_project_context
from nexaegis.core.safety import evaluate_command

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
    safety = evaluate_command(command, safe_mode=context.config.safe_mode)
    color = "red" if safety.requires_confirmation else "green"
    console.print(
        Panel.fit(
            "\n".join(
                [
                    f"Command: {command}",
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

    record = asdict(safety) | {"dry_run": dry_run, "execute_requested": execute}
    if dry_run:
        record["status"] = "dry_run"
        context.store.record_command(command, record)
        return

    if not context.config.allow_command_execution and not execute:
        record["status"] = "blocked_by_config"
        context.store.record_command(command, record)
        console.print(
            "[yellow]Command execution is disabled by config. Re-run with --execute for this "
            "explicit command after review.[/yellow]"
        )
        return

    if safety.requires_confirmation:
        if not confirm_danger and context.config.safe_mode:
            if not Confirm.ask(
                "This command is dangerous. Do you explicitly approve it?", default=False
            ):
                record["status"] = "danger_not_approved"
                context.store.record_command(command, record)
                console.print("Aborted. Command was not run.")
                return
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
            return
    elif not yes and not Confirm.ask("Run this command?", default=False):
        record["status"] = "aborted"
        context.store.record_command(command, record)
        console.print("Aborted. Command was not run.")
        return

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
