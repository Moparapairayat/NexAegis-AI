from __future__ import annotations

import typer

from nexaegis import __version__
from nexaegis.cli.commands.ask import ask_command
from nexaegis.cli.commands.ci import ci_command
from nexaegis.cli.commands.commit import commit_command
from nexaegis.cli.commands.doctor import doctor_command
from nexaegis.cli.commands.explain import explain_command
from nexaegis.cli.commands.fix import fix_app
from nexaegis.cli.commands.history import history_command
from nexaegis.cli.commands.init import init_command
from nexaegis.cli.commands.report import report_command
from nexaegis.cli.commands.risk import risk_command
from nexaegis.cli.commands.run import run_command
from nexaegis.cli.commands.security import security_command
from nexaegis.cli.commands.ui import ui_command

app = typer.Typer(
    name="nax",
    help="NexAegis AI: risk-aware AI DevOps terminal.",
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"nax {__version__}")
        raise typer.Exit


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        help="Show the installed NexAegis AI version.",
    ),
) -> None:
    """Next-generation AI defense and automation for developers."""


app.command("init")(init_command)
app.command("doctor")(doctor_command)
app.command("risk")(risk_command)
app.command("security")(security_command)
app.command("explain")(explain_command)
app.command("ask")(ask_command)
app.add_typer(fix_app, name="fix")
app.command("run")(run_command)
app.command("commit")(commit_command)
app.command("ui")(ui_command)
app.command("report")(report_command)
app.command("ci")(ci_command)
app.command("history")(history_command)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
