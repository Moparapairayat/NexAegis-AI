from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nexaegis.core.context import get_project_context
from nexaegis.scanners.risk import analyze_risk

console = Console()


def risk_command() -> None:
    """Analyze engineering risk for the current project and working tree."""
    context = get_project_context()
    result = analyze_risk(context.root, weights=context.config.risk_weights)
    context.store.record_risk_run(context.root, result.score, result.level, result.to_dict())

    color = {"low": "green", "medium": "yellow", "high": "red"}.get(result.level, "white")
    console.print(
        Panel.fit(
            f"[bold]Risk score:[/bold] [{color}]{result.score}/100[/{color}]\n"
            f"[bold]Level:[/bold] [{color}]{result.level.upper()}[/{color}]",
            title="NexAegis Risk",
            border_style=color,
        )
    )

    table = Table(title="Risk Signals")
    table.add_column("Reasons", style="bold")
    table.add_column("Recommendations")
    rows = max(len(result.reasons), len(result.recommendations))
    for index in range(rows):
        table.add_row(
            result.reasons[index] if index < len(result.reasons) else "",
            result.recommendations[index] if index < len(result.recommendations) else "",
        )
    console.print(table)
