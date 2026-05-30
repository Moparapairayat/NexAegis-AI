from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from nexaegis.core.context import get_project_context
from nexaegis.core.reporting import build_project_report, render_report

console = Console()


def report_command(
    report_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Report format: markdown, json, or sarif."),
    ] = "markdown",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write report to this path instead of stdout."),
    ] = None,
) -> None:
    """Generate a local project report in Markdown, JSON, or SARIF."""
    context = get_project_context()
    report = build_project_report(context.root, context.config)
    text = render_report(report, report_format)

    context.store.record_scan_run(context.root, report.doctor.score, report.doctor.to_dict())
    context.store.record_risk_run(
        context.root, report.risk.score, report.risk.level, report.risk.to_dict()
    )
    context.store.record_security_run(
        context.root, report.security.score, report.security.to_dict()
    )

    if output:
        target = output if output.is_absolute() else context.root / output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        console.print(f"[green]Report written:[/green] {target}")
        return

    console.out(text)
