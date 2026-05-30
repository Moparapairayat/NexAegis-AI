from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LatestRun:
    created_at: str
    score: int
    level: str | None = None
    payload_json: str = "{}"
