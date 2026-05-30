from pathlib import Path

from nexaegis.db.sqlite_store import SQLiteStore


def test_recent_runs_decodes_payload(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".nexaegis" / "nexaegis.db")
    store.initialize()
    store.record_command("uv run pytest", {"status": "dry_run"})

    rows = store.recent_runs("command_history")

    assert rows[0]["command"] == "uv run pytest"
    assert rows[0]["safety_json"]["status"] == "dry_run"
