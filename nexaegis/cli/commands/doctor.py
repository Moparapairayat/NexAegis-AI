from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nexaegis.core.context import get_project_context
from nexaegis.scanners.project import GOOD, MISSING, WARNING, scan_project

console = Console()


def doctor_command() -> None:
    """Scan project health and save the result locally."""
    context = get_project_context()
    result = scan_project(context.root)
    context.store.record_scan_run(context.root, result.score, result.to_dict())

    table = Table(title="Project Health")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")

    for check in result.checks:
        style = {GOOD: "green", WARNING: "yellow", MISSING: "red"}[check.status]
        table.add_row(check.name, f"[{style}]{check.status}[/{style}]", check.detail)

    console.print(Panel.fit(f"[bold]Health score:[/bold] {result.score}/100", border_style="cyan"))
    console.print(table)
