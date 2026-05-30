from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from nexaegis.ai.prompts import ASK_SYSTEM_PROMPT
from nexaegis.ai.provider import get_provider
from nexaegis.ai.rule_based import answer_project_question
from nexaegis.core.context import get_project_context
from nexaegis.core.paths import iter_project_paths
from nexaegis.scanners.git import status_summary

console = Console()


def ask_command(
    question: Annotated[
        str | None,
        typer.Argument(help="Question about this project."),
    ] = None,
) -> None:
    """Ask about the current project using compact local context."""
    context = get_project_context()
    text = question or console.input("Question: ").strip()
    if not text:
        console.print("[red]No question provided.[/red]")
        raise typer.Exit(code=1)

    compact_context = build_compact_context(context.root)
    if context.config.ai_provider == "rule_based":
        answer = answer_project_question(text, compact_context)
    else:
        prompt = f"Question:\n{text}\n\nLocal project context:\n{compact_context}"
        answer = get_provider(context.config).complete(prompt, system=ASK_SYSTEM_PROMPT)

    console.print(Panel(Text(answer), title="NexAegis Ask", border_style="green"))


def build_compact_context(root: Path) -> str:
    context = get_project_context(root)
    parts = [
        f"Project: {context.config.project_name}",
        f"Root: {root}",
        f"Git: {status_summary(root)}",
        "Tree:\n" + _tree_summary(root),
    ]
    readme = _read_excerpt(root / "README.md")
    if readme:
        parts.append("README excerpt:\n" + readme)
    pyproject = _read_excerpt(root / "pyproject.toml", limit=1200)
    if pyproject:
        parts.append("pyproject.toml excerpt:\n" + pyproject)
    package_json = _read_excerpt(root / "package.json", limit=1200)
    if package_json:
        parts.append("package.json excerpt:\n" + package_json)
    if latest := context.store.latest_scan():
        parts.append(f"Latest doctor score: {latest.score} at {latest.created_at}")
    if latest := context.store.latest_risk():
        parts.append(
            f"Latest risk score: {latest.score} ({latest.level}) at {latest.created_at}\n"
            f"Risk payload: {_short_json(latest.payload_json)}"
        )
    return "\n\n".join(parts)


def _tree_summary(root: Path, limit: int = 80) -> str:
    lines: list[str] = []
    for path in iter_project_paths(root):
        relative_parts = path.relative_to(root).parts
        if len(lines) >= limit:
            lines.append("...")
            break
        depth = len(relative_parts) - 1
        prefix = "  " * depth
        suffix = "/" if path.is_dir() else ""
        lines.append(f"{prefix}{path.name}{suffix}")
    return "\n".join(lines) or "(empty project)"


def _read_excerpt(path: Path, *, limit: int = 2000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:limit]


def _short_json(payload: str, limit: int = 1200) -> str:
    try:
        formatted = json.dumps(json.loads(payload), indent=2)
    except json.JSONDecodeError:
        formatted = payload
    return formatted[:limit]
