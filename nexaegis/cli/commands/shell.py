from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from nexaegis.cli.commands.run import run_checked_command
from nexaegis.core.context import get_project_context

console = Console()


def shell_command(
    execute: Annotated[
        bool,
        typer.Option(
            "--execute",
            help="Allow reviewed commands to run in this shell session.",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation for non-dangerous commands."),
    ] = False,
    timeout: Annotated[int, typer.Option("--timeout", help="Execution timeout in seconds.")] = 120,
) -> None:
    """Open an interactive NexAegis safety shell."""
    context = get_project_context()
    console.print(
        "[bold]NexAegis Shell[/bold] - type `exit` to leave. "
        "Every command is inspected before execution."
    )
    while True:
        try:
            command = console.input("[bold cyan]nax>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return

        if not command:
            continue
        if command.lower() in {"exit", "quit"}:
            return

        try:
            run_checked_command(
                context,
                command,
                execute=execute,
                yes=yes,
                confirm_danger=False,
                dry_run=False,
                timeout=timeout,
            )
        except typer.Exit as exc:
            code = exc.exit_code if isinstance(exc.exit_code, int) else 1
            console.print(f"[red]Command exited with code {code}.[/red]")
