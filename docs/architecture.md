# Architecture

NexAegis AI is organized as a local-first Python CLI with thin Typer command handlers and reusable service modules.

## Layers

- CLI: command parsing and Rich output under `nexaegis/cli/commands/`.
- Core: config, safety checks, patch application, command execution, scoring, and context.
- Policies: built-in and custom command firewall rule packs for shell and run workflows.
- Reporting: shared JSON/Markdown report generation for terminal and CI workflows.
- Scanners: project structure, Git state, risk, and security checks.
- AI: provider protocol, deterministic rule-based fallback, and local Ollama integration.
- DB: SQLite persistence for scan, risk, security, command, and fix history.
- TUI: Textual dashboard that reads latest local state.

## Data Flow

Commands create a `ProjectContext`, which loads `.nexaegis/config.yaml`, initializes `.nexaegis/nexaegis.db`, and exposes a `SQLiteStore`. Scanners return dataclasses that can be rendered in the terminal and persisted as JSON payloads.

`nax run` and `nax shell` evaluate commands with the policy-backed safety layer before execution. If execution is not enabled in config, `nax run` requires an explicit `--execute` override for that single user-requested command. Dangerous commands require human approval and are recorded in command history and the unified event log.

## Extension Points

- Add scanners by returning structured dataclasses with `to_dict()`.
- Add fix classes by producing `PatchPlan` objects.
- Add AI providers by implementing the `AIProvider` protocol.
- Add dashboard panels by reading from `SQLiteStore` or scanner modules.
- Add safe fix classes by registering a stable fix ID that maps to a deterministic `PatchPlan`.
- Add policy packs by defining `command_rules` YAML and referencing it from `custom_policy_paths`.
