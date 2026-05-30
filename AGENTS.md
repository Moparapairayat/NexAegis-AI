# Agent Instructions

## Commands

- Install dependencies: `uv sync --dev`
- Run tests: `uv run pytest`
- Run lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Try CLI locally: `uv run nax --help`
- Smoke command firewall: `uv run nax run "echo hi" --dry-run`
- Generate report: `uv run nax report --format markdown`

## Architecture

- `nexaegis/cli/commands/` contains Typer command handlers.
- `nexaegis/core/` contains config, safety, patching, execution, scoring, and context helpers.
- `nexaegis/core/reporting.py` builds automation-friendly JSON/Markdown reports.
- `nexaegis/scanners/` contains project, risk, security, and Git scanners.
- `nexaegis/ai/` contains the provider protocol plus rule-based and Ollama providers.
- `nexaegis/db/` owns SQLite persistence.
- `nexaegis/tui/` owns the Textual dashboard.

## Coding Style

- Keep code typed where reasonable.
- Prefer dataclasses or Pydantic models for structured results.
- Keep modules small and command handlers thin.
- Use Rich for terminal output.
- Handle missing optional tools gracefully.

## Safety Rules

- Never bypass dry-run behavior.
- Never apply patches without user confirmation.
- Always create backups before applying patches.
- Never print secret values.
- Never remove safety confirmations.
- Never run dangerous commands automatically.
- Keep `nax run` explicit: config gate, confirmation gate, and command history must remain intact.
- Keep `allow_command_execution` defaulted to `false`.

## Quality Rules

- Add or update focused tests for behavior changes.
- Run tests and Ruff before handing off.
- Do not hide failing tests.
- Do not broaden scanner scope in a way that reads ignored directories such as `.git`, `.nexaegis`, `.venv`, or `node_modules`.
