from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".nexaegis",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
}


def iter_project_paths(root: Path) -> Iterator[Path]:
    """Yield project paths while pruning large local state and dependency directories."""
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in IGNORED_DIRS]
        current = Path(current_root)
        for dirname in sorted(dirnames):
            yield current / dirname
        for filename in sorted(filenames):
            yield current / filename


def iter_project_files(root: Path) -> Iterator[Path]:
    for path in iter_project_paths(root):
        if path.is_file():
            yield path
