from __future__ import annotations

import subprocess
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

from nexaegis.core.config import backups_dir
from nexaegis.core.context import ProjectContext, get_project_context
from nexaegis.core.patcher import PatchPlan, SafePatcher
from nexaegis.core.policies import load_command_rules
from nexaegis.core.safety import evaluate_command
from nexaegis.scanners.project import scan_project

console = Console()

fix_app = typer.Typer(
    help="Generate, preview, apply, and roll back supported safe fixes.",
    no_args_is_help=False,
)


@dataclass(frozen=True)
class FixSuggestion:
    fix_id: str
    title: str
    risk: str
    plan: PatchPlan


@fix_app.callback(invoke_without_command=True)
def fix_command(
    ctx: typer.Context,
    issue: Annotated[
        str | None,
        typer.Option("--issue", help="Optional issue or error text to guide safe fixes."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview supported fixes without modifying files."),
    ] = False,
    apply_changes: Annotated[
        bool,
        typer.Option("--apply", help="Apply supported fixes after confirmation and backup."),
    ] = False,
    validate: Annotated[
        bool,
        typer.Option("--validate", help="Run configured validation commands after applying fixes."),
    ] = False,
) -> None:
    """Default fix behavior: preview all supported fixes unless --apply is passed."""
    if ctx.invoked_subcommand is not None:
        return
    if dry_run and apply_changes:
        console.print("[red]Choose either --dry-run or --apply, not both.[/red]")
        raise typer.Exit(code=2)
    _run_fix(issue=issue, fix_id="all", apply_changes=apply_changes, validate=validate)


@fix_app.command("list")
def list_fixes(
    issue: Annotated[
        str | None,
        typer.Option("--issue", help="Optional issue or error text to guide safe fixes."),
    ] = None,
) -> None:
    """List currently available safe fix suggestions."""
    context = get_project_context()
    suggestions = build_fix_suggestions(context.root, issue)
    table = Table(title="Safe Fix Registry")
    table.add_column("ID", style="bold")
    table.add_column("Risk")
    table.add_column("Title")
    table.add_column("Target")
    for suggestion in suggestions:
        table.add_row(
            suggestion.fix_id,
            suggestion.risk,
            suggestion.title,
            str(suggestion.plan.target_path),
        )
    if not suggestions:
        table.add_row("-", "-", "No supported safe fixes are currently available.", "-")
    console.print(table)


@fix_app.command("preview")
def preview_fix(
    fix_id: Annotated[str, typer.Argument(help="Fix ID to preview, or 'all'.")] = "all",
    issue: Annotated[
        str | None,
        typer.Option("--issue", help="Optional issue or error text to guide safe fixes."),
    ] = None,
) -> None:
    """Preview one supported fix without modifying files."""
    _run_fix(issue=issue, fix_id=fix_id, apply_changes=False, validate=False)


@fix_app.command("apply")
def apply_fix(
    fix_id: Annotated[str, typer.Argument(help="Fix ID to apply, or 'all'.")] = "all",
    issue: Annotated[
        str | None,
        typer.Option("--issue", help="Optional issue or error text to guide safe fixes."),
    ] = None,
    validate: Annotated[
        bool,
        typer.Option("--validate", help="Run configured validation commands after applying fixes."),
    ] = False,
) -> None:
    """Apply one supported fix after confirmation and backup."""
    _run_fix(issue=issue, fix_id=fix_id, apply_changes=True, validate=validate)


@fix_app.command("rollback")
def rollback_fix(
    rollback_target: Annotated[
        str,
        typer.Argument(help="Rollback metadata path, or 'latest'."),
    ] = "latest",
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip rollback confirmation.")] = False,
) -> None:
    """Roll back a previously applied safe fix."""
    context = get_project_context()
    backup_root = backups_dir(context.root).resolve()
    if rollback_target == "latest":
        metadata = SafePatcher.latest_rollback_metadata(backup_root)
        if metadata is None:
            console.print("[yellow]No rollback metadata found.[/yellow]")
            return
    else:
        metadata = Path(rollback_target)
        metadata = metadata if metadata.is_absolute() else context.root / metadata
        metadata = metadata.resolve()

    if not metadata.is_relative_to(backup_root):
        console.print("[red]Rollback metadata must be inside .nexaegis/backups.[/red]")
        raise typer.Exit(code=1)
    if not metadata.exists():
        console.print(f"[red]Rollback metadata not found:[/red] {metadata}")
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            f"Rollback metadata: {metadata}\nProject: {context.root}",
            title="Rollback Confirmation",
            border_style="yellow",
        )
    )
    if not yes and not Confirm.ask("Restore files from this rollback metadata?", default=False):
        console.print("Aborted. No files were modified.")
        return

    result = SafePatcher(context.root).rollback(metadata)
    context.store.record_fix(
        "rollback",
        [
            *(str(path.relative_to(context.root)) for path in result.restored_files),
            *(str(path.relative_to(context.root)) for path in result.deleted_files),
        ],
        backup_path=metadata.parent,
        result={
            "restored": len(result.restored_files),
            "deleted": len(result.deleted_files),
            "metadata": str(metadata),
        },
    )
    console.print(
        f"[green]Rollback complete.[/green] Restored {len(result.restored_files)}, "
        f"deleted {len(result.deleted_files)}."
    )
    if result.current_backup_dir:
        console.print(f"[yellow]Pre-rollback file backup:[/yellow] {result.current_backup_dir}")


def _run_fix(*, issue: str | None, fix_id: str, apply_changes: bool, validate: bool) -> None:
    context = get_project_context()
    suggestions = select_fix_suggestions(build_fix_suggestions(context.root, issue), fix_id)
    if not suggestions:
        console.print("[yellow]No matching supported safe fixes were found.[/yellow]")
        return

    patcher = SafePatcher(context.root)
    for suggestion in suggestions:
        diff = patcher.dry_run(suggestion.plan)
        console.print(
            Panel(
                Text(diff or "(no diff)"),
                title=f"{suggestion.fix_id}: {suggestion.title}",
                border_style="cyan",
            )
        )

    if not apply_changes:
        console.print("[bold]Dry run only.[/bold] No files were modified.")
        return

    if not context.config.allow_apply_patch:
        console.print("[red]Patch application is disabled by config: allow_apply_patch=false[/red]")
        raise typer.Exit(code=1)

    affected = ", ".join(str(suggestion.plan.target_path) for suggestion in suggestions)
    risk = max((suggestion.risk for suggestion in suggestions), default="low")
    console.print(
        Panel.fit(
            f"Affected files: {affected}\nRisk level: {risk}\nBackups: {backups_dir(context.root)}",
            title="Apply Confirmation",
            border_style="yellow",
        )
    )
    if not Confirm.ask("Apply these supported patches?", default=False):
        console.print("Aborted. No files were modified.")
        return

    batch = patcher.apply_many(
        [suggestion.plan for suggestion in suggestions],
        backups_dir(context.root),
    )
    context.store.record_fix(
        "apply",
        [str(result.target_path.relative_to(context.root)) for result in batch.results],
        backup_path=batch.rollback_metadata_path.parent,
        result={
            "count": len(batch.results),
            "rollback_metadata": str(batch.rollback_metadata_path),
        },
    )
    console.print(
        "[green]Patches applied with backups recorded.[/green]\n"
        f"Rollback: {batch.rollback_metadata_path}"
    )
    if validate or context.config.run_validation_after_fix:
        passed = _run_validation_commands(context)
        if not passed:
            console.print(
                "[red]Validation failed after patch application.[/red] "
                f"Use `nax fix rollback {batch.rollback_metadata_path}` if you want to restore."
            )
            raise typer.Exit(code=1)


def select_fix_suggestions(suggestions: list[FixSuggestion], fix_id: str) -> list[FixSuggestion]:
    if fix_id == "all":
        return suggestions
    return [suggestion for suggestion in suggestions if suggestion.fix_id == fix_id]


def build_fix_plans(project_root: Path, issue: str | None = None) -> list[PatchPlan]:
    return [suggestion.plan for suggestion in build_fix_suggestions(project_root, issue)]


def build_fix_suggestions(project_root: Path, issue: str | None = None) -> list[FixSuggestion]:
    root = project_root.resolve()
    scan = scan_project(root)
    suggestions: list[FixSuggestion] = []
    issue_text = (issue or "").strip()

    gitignore = root / ".gitignore"
    gitignore_text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if ".env" not in {line.strip() for line in gitignore_text.splitlines()}:
        new_gitignore = gitignore_text
        if new_gitignore and not new_gitignore.endswith("\n"):
            new_gitignore += "\n"
        new_gitignore += ".env\n"
        suggestions.append(
            FixSuggestion(
                fix_id="ignore-env",
                title="Ignore local .env files",
                risk="low",
                plan=PatchPlan(
                    target_path=Path(".gitignore"),
                    new_content=new_gitignore,
                    description="Ignore local .env files",
                ),
            )
        )

    if not scan.has_good("Environment example"):
        suggestions.append(
            FixSuggestion(
                fix_id="env-example",
                title="Add .env.example template",
                risk="low",
                plan=PatchPlan(
                    target_path=Path(".env.example"),
                    new_content="# Copy to .env and fill in project-local values.\n# API_KEY=\n",
                    description="Add .env.example template",
                ),
            )
        )

    readme = root / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        has_setup_guidance = any(
            marker in text for marker in ("## Setup", "### Setup", "## Install", "## Quickstart")
        )
        if not has_setup_guidance:
            setup = "\n\n## Setup\n\n```bash\nuv sync\nuv run pytest\n```\n"
            suggestions.append(
                FixSuggestion(
                    fix_id="readme-setup",
                    title="Add README setup section",
                    risk="low",
                    plan=PatchPlan(
                        target_path=Path("README.md"),
                        new_content=text.rstrip() + setup,
                        description="Add README setup section",
                    ),
                )
            )

    if issue_text and "ModuleNotFoundError" in issue_text:
        console.print(
            "[yellow]Detected a missing dependency issue. NexAegis will suggest the install command in "
            "`nax explain`; it will not edit dependency files automatically yet.[/yellow]"
        )

    return suggestions


def _run_validation_commands(context: ProjectContext) -> bool:
    commands = [command.strip() for command in context.config.fix_validation_commands if command]
    if not commands:
        console.print("[yellow]No validation commands are configured.[/yellow]")
        return True

    rules = load_command_rules(context.config, context.root)
    for command in commands:
        safety = evaluate_command(command, safe_mode=context.config.safe_mode, rules=rules)
        record = asdict(safety) | {"status": "validation_pending"}
        if safety.requires_confirmation or not safety.allowed:
            record["status"] = "validation_blocked"
            context.store.record_command(command, record)
            console.print(
                f"[red]Validation command blocked by policy:[/red] {command}\n"
                f"Reason: {safety.reason}"
            )
            return False

        console.print(f"[cyan]Validation:[/cyan] {command}")
        result = subprocess.run(
            command,
            cwd=context.root,
            shell=True,
            check=False,
        )
        record["status"] = "validation_passed" if result.returncode == 0 else "validation_failed"
        record["returncode"] = result.returncode
        context.store.record_command(command, record)
        if result.returncode != 0:
            return False

    return True
