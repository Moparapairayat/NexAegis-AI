from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from nexaegis.core.context import get_project_context

console = Console()

TABLE_MAP = {
    "doctor": "scan_runs",
    "risk": "risk_runs",
    "security": "security_runs",
    "commands": "command_history",
    "fixes": "fix_history",
}


def history_command(
    kind: Annotated[
        str,
        typer.Argument(help="History kind: doctor, risk, security, commands, fixes."),
    ] = "risk",
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of rows to show.")] = 10,
) -> None:
    """Show recent local NexAegis memory entries."""
    table_name = TABLE_MAP.get(kind)
    if table_name is None:
        console.print("[red]History kind must be: doctor, risk, security, commands, fixes[/red]")
        raise typer.Exit(code=2)

    context = get_project_context()
    rows = context.store.recent_runs(table_name, limit=limit)
    table = Table(title=f"NexAegis History: {kind}")
    table.add_column("ID")
    table.add_column("Created")
    table.add_column("Summary")

    for row in rows:
        table.add_row(str(row.get("id", "")), str(row.get("created_at", "")), escape(_summary(row)))
    if not rows:
        table.add_row("-", "-", "No history yet.")
    console.print(table)


def _summary(row: dict[str, object]) -> str:
    if "score" in row:
        level = f" ({row['level']})" if row.get("level") else ""
        return f"score={row['score']}{level}"
    if "command" in row:
        payload = row.get("safety_json")
        status = payload.get("status") if isinstance(payload, dict) else None
        return f"{row['command']} [{status or 'recorded'}]"
    if "action" in row:
        return f"{row['action']} backup={row.get('backup_path') or 'n/a'}"
    return "recorded"
