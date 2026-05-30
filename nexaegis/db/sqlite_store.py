from __future__ import annotations

import json
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nexaegis.db.models import LatestRun

SCHEMA_VERSION = 2


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS scan_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    status_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS risk_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    level TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS security_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS command_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    command TEXT NOT NULL,
                    safety_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fix_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    files_json TEXT NOT NULL,
                    backup_path TEXT,
                    result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    project_path TEXT,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_scan_runs_created_at
                    ON scan_runs(created_at);
                CREATE INDEX IF NOT EXISTS idx_risk_runs_created_at
                    ON risk_runs(created_at);
                CREATE INDEX IF NOT EXISTS idx_security_runs_created_at
                    ON security_runs(created_at);
                CREATE INDEX IF NOT EXISTS idx_command_history_created_at
                    ON command_history(created_at);
                CREATE INDEX IF NOT EXISTS idx_fix_history_created_at
                    ON fix_history(created_at);
                CREATE INDEX IF NOT EXISTS idx_event_log_type_created_at
                    ON event_log(event_type, created_at);
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, self.now()),
            )

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat()

    def schema_version(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def record_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        project_path: Path | None = None,
        summary: str = "",
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO event_log
                    (created_at, event_type, project_path, summary, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.now(),
                    event_type,
                    str(project_path) if project_path else None,
                    summary,
                    json.dumps(payload),
                ),
            )

    def record_scan_run(self, project_path: Path, score: int, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO scan_runs (created_at, project_path, score, status_json) VALUES (?, ?, ?, ?)",
                (self.now(), str(project_path), score, json.dumps(payload)),
            )
        self.record_event(
            "scan",
            {"score": score, "payload": payload},
            project_path=project_path,
            summary=f"Doctor score {score}/100",
        )

    def record_risk_run(
        self, project_path: Path, score: int, level: str, payload: dict[str, Any]
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO risk_runs (created_at, project_path, score, level, result_json) VALUES (?, ?, ?, ?, ?)",
                (self.now(), str(project_path), score, level, json.dumps(payload)),
            )
        self.record_event(
            "risk",
            {"score": score, "level": level, "payload": payload},
            project_path=project_path,
            summary=f"Risk {level} ({score}/100)",
        )

    def record_security_run(self, project_path: Path, score: int, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO security_runs (created_at, project_path, score, result_json) VALUES (?, ?, ?, ?)",
                (self.now(), str(project_path), score, json.dumps(payload)),
            )
        self.record_event(
            "security",
            {"score": score, "payload": payload},
            project_path=project_path,
            summary=f"Security score {score}/100",
        )

    def record_command(self, command: str, safety: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO command_history (created_at, command, safety_json) VALUES (?, ?, ?)",
                (self.now(), command, json.dumps(safety)),
            )
        self.record_event(
            "command",
            {"command": command, "safety": safety},
            summary=f"Command {safety.get('status', 'inspected')}: {command}",
        )

    def record_fix(
        self,
        action: str,
        files: list[str],
        *,
        backup_path: Path | None,
        result: dict[str, Any],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO fix_history (created_at, action, files_json, backup_path, result_json) VALUES (?, ?, ?, ?, ?)",
                (
                    self.now(),
                    action,
                    json.dumps(files),
                    str(backup_path) if backup_path else None,
                    json.dumps(result),
                ),
            )
        self.record_event(
            "fix",
            {
                "action": action,
                "files": files,
                "backup_path": str(backup_path) if backup_path else None,
                "result": result,
            },
            summary=f"Fix {action}: {len(files)} file(s)",
        )

    def latest_scan(self) -> LatestRun | None:
        return self._latest("scan_runs", "status_json")

    def latest_risk(self) -> LatestRun | None:
        return self._latest("risk_runs", "result_json", level_column="level")

    def latest_security(self) -> LatestRun | None:
        return self._latest("security_runs", "result_json")

    def recent_runs(self, table: str, *, limit: int = 10) -> list[dict[str, Any]]:
        allowed = {
            "scan_runs": "status_json",
            "risk_runs": "result_json",
            "security_runs": "result_json",
            "command_history": "safety_json",
            "fix_history": "result_json",
            "event_log": "payload_json",
        }
        payload_column = allowed.get(table)
        if payload_column is None:
            raise ValueError(f"Unsupported history table: {table}")
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            columns = [
                description[0]
                for description in conn.execute(f"SELECT * FROM {table} LIMIT 0").description
            ]

        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(zip(columns, row, strict=True))
            raw_payload = item.get(payload_column)
            if isinstance(raw_payload, str):
                with suppress(json.JSONDecodeError):
                    item[payload_column] = json.loads(raw_payload)
            results.append(item)
        return results

    def recent_events(self, *, limit: int = 20, event_type: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM event_log"
        params: tuple[object, ...] = ()
        if event_type:
            query += " WHERE event_type = ?"
            params = (event_type,)
        query += " ORDER BY id DESC LIMIT ?"
        params = (*params, limit)
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            columns = [
                description[0]
                for description in conn.execute("SELECT * FROM event_log LIMIT 0").description
            ]

        events: list[dict[str, Any]] = []
        for row in rows:
            item = dict(zip(columns, row, strict=True))
            raw_payload = item.get("payload_json")
            if isinstance(raw_payload, str):
                with suppress(json.JSONDecodeError):
                    item["payload_json"] = json.loads(raw_payload)
            events.append(item)
        return events

    def _latest(
        self,
        table: str,
        payload_column: str,
        *,
        level_column: str | None = None,
    ) -> LatestRun | None:
        level_expr = f", {level_column}" if level_column else ""
        query = (
            f"SELECT created_at, score, {payload_column}{level_expr} "
            f"FROM {table} ORDER BY id DESC LIMIT 1"
        )
        with self.connect() as conn:
            row = conn.execute(query).fetchone()
        if row is None:
            return None
        if level_column:
            return LatestRun(created_at=row[0], score=row[1], payload_json=row[2], level=row[3])
        return LatestRun(created_at=row[0], score=row[1], payload_json=row[2])
