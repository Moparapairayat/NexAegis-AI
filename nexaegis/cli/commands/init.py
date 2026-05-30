from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from nexaegis.core.config import config_path, db_path, write_default_config
from nexaegis.db.sqlite_store import SQLiteStore

console = Console()


def init_command() -> None:
    """Initialize NexAegis AI state in the current project."""
    root = Path.cwd().resolve()
    config_file = write_default_config(root, overwrite=False)
    database = SQLiteStore(db_path(root))
    database.initialize()

    console.print(
        Panel.fit(
            "\n".join(
                [
                    "[bold green]NexAegis AI initialized[/bold green]",
                    f"Project: [bold]{root.name}[/bold]",
                    f"Config: {config_file.relative_to(root)}",
                    f"Database: {config_path(root).parent.joinpath('nexaegis.db').relative_to(root)}",
                    "Safe mode: enabled",
                    "AI provider: rule_based",
                ]
            ),
            title="nax init",
            border_style="green",
        )
    )
