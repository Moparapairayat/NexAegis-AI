from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nexaegis.core.context import get_project_context
from nexaegis.scanners.security import scan_security

console = Console()


def security_command() -> None:
    """Run optional security scanners and built-in secret hygiene checks."""
    context = get_project_context()
    result = scan_security(context.root)
    context.store.record_security_run(context.root, result.score, result.to_dict())

    console.print(
        Panel.fit(
            f"[bold]Security score:[/bold] {result.score}/100",
            title="NexAegis Security",
            border_style="magenta",
        )
    )

    tools = Table(title="External Scanner Status")
    tools.add_column("Tool", style="bold")
    tools.add_column("Status")
    tools.add_column("Findings")
    tools.add_column("Suggestion")
    for tool in result.tools:
        status_style = "green" if tool.installed and tool.finding_count == 0 else "yellow"
        tools.add_row(
            tool.name,
            f"[{status_style}]{tool.status}[/{status_style}]",
            str(tool.finding_count),
            tool.suggestion,
        )
    console.print(tools)

    findings = Table(title="Built-in Findings")
    findings.add_column("Severity", style="bold")
    findings.add_column("Title")
    findings.add_column("Path")
    findings.add_column("Detail")
    if not result.findings:
        findings.add_row("Good", "No built-in security issues detected.", "", "")
    else:
        for finding in result.findings:
            style = {"high": "red", "medium": "yellow", "low": "cyan"}.get(
                finding.severity.lower(),
                "white",
            )
            findings.add_row(
                f"[{style}]{finding.severity}[/{style}]",
                finding.title,
                finding.path or "",
                finding.detail or "",
            )
    console.print(findings)
