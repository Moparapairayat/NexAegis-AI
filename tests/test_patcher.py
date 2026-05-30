from pathlib import Path

import pytest

from nexaegis.core.patcher import PatchPlan, SafePatcher


def test_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    target = tmp_path / "README.md"
    target.write_text("old\n", encoding="utf-8")
    patcher = SafePatcher(tmp_path)

    diff = patcher.dry_run(
        PatchPlan(target_path=Path("README.md"), new_content="new\n", description="update readme")
    )

    assert "-old" in diff
    assert "+new" in diff
    assert target.read_text(encoding="utf-8") == "old\n"


def test_apply_creates_backup(tmp_path: Path) -> None:
    target = tmp_path / "README.md"
    target.write_text("old\n", encoding="utf-8")
    patcher = SafePatcher(tmp_path)

    result = patcher.apply(
        PatchPlan(target_path=Path("README.md"), new_content="new\n", description="update readme"),
        tmp_path / ".nexaegis" / "backups",
    )

    assert target.read_text(encoding="utf-8") == "new\n"
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert result.rollback_metadata_path.exists()


def test_rollback_restores_modified_file_and_deletes_created_file(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("old\n", encoding="utf-8")
    patcher = SafePatcher(tmp_path)

    batch = patcher.apply_many(
        [
            PatchPlan(target_path=Path("README.md"), new_content="new\n", description="update"),
            PatchPlan(
                target_path=Path(".env.example"), new_content="API_KEY=\n", description="create"
            ),
        ],
        tmp_path / ".nexaegis" / "backups",
    )

    result = patcher.rollback(batch.rollback_metadata_path)

    assert readme.read_text(encoding="utf-8") == "old\n"
    assert not (tmp_path / ".env.example").exists()
    assert readme in result.restored_files
    assert tmp_path / ".env.example" in result.deleted_files
    assert result.current_backup_dir is not None
    assert (result.current_backup_dir / "README.md").exists()


def test_apply_many_rejects_duplicate_targets_before_writing(tmp_path: Path) -> None:
    target = tmp_path / "README.md"
    target.write_text("old\n", encoding="utf-8")
    patcher = SafePatcher(tmp_path)

    with pytest.raises(ValueError, match="duplicate target"):
        patcher.apply_many(
            [
                PatchPlan(target_path=Path("README.md"), new_content="one\n", description="one"),
                PatchPlan(target_path=Path("README.md"), new_content="two\n", description="two"),
            ],
            tmp_path / ".nexaegis" / "backups",
        )

    assert target.read_text(encoding="utf-8") == "old\n"


def test_apply_many_preflights_all_targets_before_writing(tmp_path: Path) -> None:
    target = tmp_path / "README.md"
    target.write_text("old\n", encoding="utf-8")
    patcher = SafePatcher(tmp_path)

    with pytest.raises(ValueError, match="outside project root"):
        patcher.apply_many(
            [
                PatchPlan(target_path=Path("README.md"), new_content="new\n", description="safe"),
                PatchPlan(target_path=Path("..") / "escape.txt", new_content="bad\n", description="bad"),
            ],
            tmp_path / ".nexaegis" / "backups",
        )

    assert target.read_text(encoding="utf-8") == "old\n"
