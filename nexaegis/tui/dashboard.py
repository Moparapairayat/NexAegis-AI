from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from nexaegis.core.context import get_project_context
from nexaegis.scanners.git import status_summary


class DashboardCard(Static):
    def __init__(self, title: str, value: str) -> None:
        super().__init__(f"[b]{title}[/b]\n{value}", classes="card")


class NexAegisDashboard(App[None]):
    CSS = """
    Screen {
        background: #101418;
    }
    Grid {
        grid-size: 2;
        grid-gutter: 1 2;
        padding: 1 2;
    }
    .card {
        border: solid #5eb1bf;
        padding: 1 2;
        min-height: 5;
        background: #172026;
        color: #f3f7f8;
    }
    .panel {
        border: solid #5eb1bf;
        padding: 1 2;
        background: #172026;
        color: #f3f7f8;
    }
    """

    BINDINGS: ClassVar = [("q", "quit", "Quit")]

    def __init__(self, project_root: Path | None = None) -> None:
        super().__init__()
        self.project_root = project_root or Path.cwd()

    def compose(self) -> ComposeResult:
        context = get_project_context(self.project_root)
        scan = context.store.latest_scan()
        risk = context.store.latest_risk()
        security = context.store.latest_security()

        yield Header(show_clock=True)
        with TabbedContent(initial="overview"):
            with TabPane("Overview", id="overview"), Grid():
                yield DashboardCard("Project", context.config.project_name)
                yield DashboardCard("Health score", str(scan.score) if scan else "No scan yet")
                yield DashboardCard(
                    "Risk score",
                    f"{risk.score} ({risk.level})" if risk and risk.level else "No risk scan yet",
                )
                yield DashboardCard(
                    "Security score",
                    str(security.score) if security else "No scan yet",
                )
                yield DashboardCard("Git status", status_summary(context.root))
                yield DashboardCard("AI provider", context.config.ai_provider)
                yield DashboardCard("Last scan time", scan.created_at if scan else "No scan yet")
                yield DashboardCard(
                    "Safe mode",
                    "enabled" if context.config.safe_mode else "disabled",
                )
            with TabPane("Risk", id="risk"):
                yield Static(_payload_excerpt(risk.payload_json if risk else ""), classes="panel")
            with TabPane("Security", id="security"):
                yield Static(
                    _payload_excerpt(security.payload_json if security else ""),
                    classes="panel",
                )
            with TabPane("History", id="history"):
                yield Static(_history_summary(context.root), classes="panel")
        yield Footer()


def _payload_excerpt(payload: str, limit: int = 3000) -> str:
    return payload[:limit] if payload else "No scan history yet."


def _history_summary(project_root: Path) -> str:
    context = get_project_context(project_root)
    lines: list[str] = []
    for label, table in (
        ("Doctor", "scan_runs"),
        ("Risk", "risk_runs"),
        ("Security", "security_runs"),
        ("Commands", "command_history"),
        ("Fixes", "fix_history"),
    ):
        rows = context.store.recent_runs(table, limit=3)
        entry = "entry" if len(rows) == 1 else "entries"
        lines.append(f"{label}: {len(rows)} recent {entry}")
    return "\n".join(lines)
