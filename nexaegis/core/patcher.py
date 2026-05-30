from __future__ import annotations

import difflib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PatchPlan:
    target_path: Path
    new_content: str
    description: str


@dataclass(frozen=True)
class PatchApplyResult:
    target_path: Path
    backup_path: Path | None
    created: bool
    rollback_metadata_path: Path


@dataclass(frozen=True)
class PatchBatchResult:
    rollback_metadata_path: Path
    results: list[PatchApplyResult]


@dataclass(frozen=True)
class RollbackResult:
    metadata_path: Path
    restored_files: list[Path]
    deleted_files: list[Path]
    current_backup_dir: Path | None = None


class SafePatcher:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def resolve_target(self, target_path: Path) -> Path:
        path = target_path if target_path.is_absolute() else self.project_root / target_path
        resolved = path.resolve()
        if not resolved.is_relative_to(self.project_root):
            raise ValueError(f"Patch target is outside project root: {target_path}")
        return resolved

    def dry_run(self, plan: PatchPlan) -> str:
        target = self.resolve_target(plan.target_path)
        old_content = target.read_text(encoding="utf-8") if target.exists() else ""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = plan.new_content.splitlines(keepends=True)
        return "".join(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=str(plan.target_path),
                tofile=str(plan.target_path),
            )
        )

    def apply(self, plan: PatchPlan, backup_root: Path) -> PatchApplyResult:
        batch = self.apply_many([plan], backup_root)
        return batch.results[0]

    def apply_many(self, plans: list[PatchPlan], backup_root: Path) -> PatchBatchResult:
        if not plans:
            raise ValueError("No patch plans were provided.")

        backup_dir = self._new_backup_dir(backup_root)
        results: list[PatchApplyResult] = []
        changes: list[dict[str, Any]] = []

        metadata_path = backup_dir / "rollback.json"

        for plan in plans:
            target = self.resolve_target(plan.target_path)
            created = not target.exists()
            backup_path: Path | None = None

            if target.exists():
                relative = target.relative_to(self.project_root)
                backup_path = backup_dir / "files" / relative
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_path)

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(plan.new_content, encoding="utf-8")

            results.append(
                PatchApplyResult(
                    target_path=target,
                    backup_path=backup_path,
                    created=created,
                    rollback_metadata_path=metadata_path,
                )
            )
            changes.append(
                {
                    "target_path": target.relative_to(self.project_root).as_posix(),
                    "backup_path": str(backup_path) if backup_path else None,
                    "created": created,
                    "description": plan.description,
                }
            )

        metadata = {
            "version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "project_root": str(self.project_root),
            "changes": changes,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return PatchBatchResult(rollback_metadata_path=metadata_path, results=results)

    def rollback(self, metadata_path: Path) -> RollbackResult:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        changes = metadata.get("changes")
        if not isinstance(changes, list):
            changes = [metadata]

        restored: list[Path] = []
        deleted: list[Path] = []
        current_backup_dir = metadata_path.parent / "pre_rollback_current"
        for change in reversed(changes):
            if not isinstance(change, dict):
                continue
            target_raw = change.get("target_path")
            if not isinstance(target_raw, str):
                continue
            target = self.resolve_target(Path(target_raw))
            created = bool(change.get("created"))
            backup_raw = change.get("backup_path")

            if created:
                if target.exists():
                    self._backup_current_before_rollback(target, current_backup_dir)
                    target.unlink()
                    deleted.append(target)
                continue

            if not isinstance(backup_raw, str):
                continue
            backup = Path(backup_raw)
            if not backup.exists():
                raise FileNotFoundError(f"Rollback backup is missing: {backup}")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                self._backup_current_before_rollback(target, current_backup_dir)
            shutil.copy2(backup, target)
            restored.append(target)

        return RollbackResult(
            metadata_path=metadata_path,
            restored_files=restored,
            deleted_files=deleted,
            current_backup_dir=current_backup_dir if current_backup_dir.exists() else None,
        )

    @staticmethod
    def latest_rollback_metadata(backup_root: Path) -> Path | None:
        if not backup_root.exists():
            return None
        candidates = sorted(backup_root.glob("*/rollback.json"), reverse=True)
        return candidates[0] if candidates else None

    @staticmethod
    def _new_backup_dir(backup_root: Path) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup_dir = backup_root / timestamp
        backup_dir.mkdir(parents=True, exist_ok=False)
        return backup_dir

    def _backup_current_before_rollback(self, target: Path, current_backup_dir: Path) -> None:
        relative = target.relative_to(self.project_root)
        backup = current_backup_dir / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
