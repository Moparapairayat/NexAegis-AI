from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from nexaegis.scanners.git import changed_files


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_changed_files_ignores_nexaegis_state(tmp_path: Path) -> None:
    subprocess.run(["git", "-C", str(tmp_path), "init"], check=True, capture_output=True)
    (tmp_path / ".nexaegis").mkdir()
    (tmp_path / ".nexaegis" / "config.yaml").write_text("project_name: demo\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    assert changed_files(tmp_path) == ["README.md"]
