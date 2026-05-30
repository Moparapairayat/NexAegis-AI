from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from nexaegis.core.context import get_project_context
from nexaegis.core.reporting import build_project_report, render_report

console = Console()

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def ci_command(
    min_health: Annotated[
        int | None,
        typer.Option("--min-health", help="Minimum passing doctor score."),
    ] = None,
    min_security: Annotated[
        int | None,
        typer.Option("--min-security", help="Minimum passing security score."),
    ] = None,
    max_risk: Annotated[
        str | None,
        typer.Option("--max-risk", help="Maximum allowed risk level: low, medium, high."),
    ] = None,
    report_format: Annotated[
        str,
        typer.Option("--format", help="Optional report format: markdown, json, or sarif."),
    ] = "markdown",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write CI report to this path."),
    ] = None,
) -> None:
    """Run non-interactive CI gates for health, risk, security, and reports."""
    context = get_project_context()
    health_gate = min_health if min_health is not None else context.config.ci_min_health_score
    security_gate = (
        min_security if min_security is not None else context.config.ci_min_security_score
    )
    risk_gate = (max_risk or context.config.ci_max_risk_level).lower()
    if risk_gate not in RISK_ORDER:
        console.print("[red]--max-risk must be one of: low, medium, high[/red]")
        raise typer.Exit(code=2)

    report = build_project_report(context.root, context.config)
    context.store.record_scan_run(context.root, report.doctor.score, report.doctor.to_dict())
    context.store.record_risk_run(
        context.root, report.risk.score, report.risk.level, report.risk.to_dict()
    )
    context.store.record_security_run(
        context.root, report.security.score, report.security.to_dict()
    )

    checks = [
        ("Health", report.doctor.score >= health_gate, f"{report.doctor.score} >= {health_gate}"),
        (
            "Risk",
            RISK_ORDER[report.risk.level] <= RISK_ORDER[risk_gate],
            f"{report.risk.level} <= {risk_gate}",
        ),
        (
            "Security",
            report.security.score >= security_gate,
            f"{report.security.score} >= {security_gate}",
        ),
    ]

    table = Table(title="NexAegis CI Gates")
    table.add_column("Gate", style="bold")
    table.add_column("Result")
    table.add_column("Condition")
    for name, passed, condition in checks:
        table.add_row(name, "[green]pass[/green]" if passed else "[red]fail[/red]", condition)
    console.print(table)

    if output:
        target = output if output.is_absolute() else context.root / output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_report(report, report_format), encoding="utf-8")
        console.print(f"[green]CI report written:[/green] {target}")

    if not all(passed for _, passed, _ in checks):
        raise typer.Exit(code=1)
