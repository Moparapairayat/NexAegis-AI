from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from nexaegis.ai.prompts import EXPLAIN_SYSTEM_PROMPT
from nexaegis.ai.provider import get_provider
from nexaegis.ai.rule_based import explain_error, format_explanation
from nexaegis.core.context import get_project_context

console = Console()


def explain_command(
    error: Annotated[
        str | None,
        typer.Argument(help="Error text to explain. Omit to paste interactively."),
    ] = None,
) -> None:
    """Explain an error without running commands."""
    context = get_project_context()
    error_text = error or console.input("Paste error text: ").strip()
    if not error_text:
        console.print("[red]No error text provided.[/red]")
        raise typer.Exit(code=1)

    if context.config.ai_provider == "rule_based":
        output = format_explanation(explain_error(error_text))
    else:
        output = get_provider(context.config).complete(error_text, system=EXPLAIN_SYSTEM_PROMPT)
    console.print(Panel(Text(output), title="Explanation", border_style="cyan"))
