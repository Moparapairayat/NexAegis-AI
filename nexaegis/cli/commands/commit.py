from __future__ import annotations

import subprocess

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from nexaegis.ai.rule_based import suggest_commit_message
from nexaegis.core.context import get_project_context
from nexaegis.scanners.git import changed_files, diff_stat, is_git_repo

console = Console()


def commit_command() -> None:
    """Suggest a safe commit message and optionally commit if execution is enabled."""
    context = get_project_context()
    if not is_git_repo(context.root):
        console.print("[red]This project is not a Git repository.[/red]")
        raise typer.Exit(code=1)

    files = changed_files(context.root)
    if not files:
        console.print("[green]Working tree is clean.[/green]")
        return

    message = suggest_commit_message(files, diff_stat(context.root))
    table = Table(title="Changed Files")
    table.add_column("Path")
    for file in files:
        table.add_row(file)
    console.print(table)
    console.print(Panel(message, title="Suggested Commit Message", border_style="cyan"))

    if not context.config.allow_command_execution:
        console.print(
            "[yellow]Command execution is disabled by config. Suggested command:[/yellow]\n"
            f'git add {" ".join(files)} && git commit -m "{message}"'
        )
        return

    if not Confirm.ask("Stage these files and create the commit?", default=False):
        console.print("Aborted. No commit was created.")
        return

    add_result = subprocess.run(
        ["git", "-C", str(context.root), "add", "--", *files],
        text=True,
        capture_output=True,
        check=False,
    )
    if add_result.returncode != 0:
        console.print(f"[red]git add failed:[/red]\n{add_result.stderr}")
        raise typer.Exit(code=add_result.returncode)

    result = subprocess.run(
        ["git", "-C", str(context.root), "commit", "-m", message],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        console.print("[green]Commit created.[/green]")
    else:
        console.print(f"[red]git commit failed:[/red]\n{result.stderr}")
