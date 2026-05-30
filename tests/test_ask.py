from pathlib import Path

from nexaegis.cli.commands.ask import _tree_summary


def test_tree_summary_prunes_ignored_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text("", encoding="utf-8")

    summary = _tree_summary(tmp_path)

    assert "src/" in summary
    assert "app.py" in summary
    assert "node_modules" not in summary
