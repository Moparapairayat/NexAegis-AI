from __future__ import annotations


def ui_command() -> None:
    """Open the local Textual dashboard."""
    from nexaegis.tui.dashboard import NexAegisDashboard

    NexAegisDashboard().run()
