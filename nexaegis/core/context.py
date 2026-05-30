from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nexaegis.core.config import NexAegisConfig, db_path, ensure_state_dir, load_config
from nexaegis.db.sqlite_store import SQLiteStore


@dataclass(frozen=True)
class ProjectContext:
    root: Path
    config: NexAegisConfig
    store: SQLiteStore


def get_project_context(
    project_root: Path | None = None, *, initialize_db: bool = True
) -> ProjectContext:
    root = (project_root or Path.cwd()).resolve()
    ensure_state_dir(root)
    config = load_config(root)
    store = SQLiteStore(db_path(root))
    if initialize_db:
        store.initialize()
    return ProjectContext(root=root, config=config, store=store)
