# Architecture

NexAegis AI is organized as a local-first Python CLI with thin Typer command handlers and reusable service modules.

## Layers

- CLI: command parsing and Rich output under `nexaegis/cli/commands/`.
- Core: config, safety checks, patch application, command execution, scoring, and context.
- Reporting: shared JSON/Markdown report generation for terminal and CI workflows.
- Scanners: project structure, Git state, risk, and security checks.
- AI: provider protocol, deterministic rule-based fallback, and local Ollama integration.
- DB: SQLite persistence for scan, risk, security, command, and fix history.
- TUI: Textual dashboard that reads latest local state.

## Data Flow

Commands create a `ProjectContext`, which loads `.nexaegis/config.yaml`, initializes `.nexaegis/nexaegis.db`, and exposes a `SQLiteStore`. Scanners return dataclasses that can be rendered in the terminal and persisted as JSON payloads.

`nax run` evaluates commands with the safety layer before execution. If execution is not enabled in config, it requires an explicit `--execute` override for that single user-requested command. Dangerous commands require human approval and are recorded in command history.

## Extension Points

- Add scanners by returning structured dataclasses with `to_dict()`.
- Add fix classes by producing `PatchPlan` objects.
- Add AI providers by implementing the `AIProvider` protocol.
- Add dashboard panels by reading from `SQLiteStore` or scanner modules.
- Add safe fix classes by registering a stable fix ID that maps to a deterministic `PatchPlan`.
