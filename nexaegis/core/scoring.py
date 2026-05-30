from __future__ import annotations


def clamp_score(score: int | float) -> int:
    return max(0, min(100, round(score)))


def risk_level(score: int) -> str:
    if score <= 30:
        return "low"
    if score <= 65:
        return "medium"
    return "high"
