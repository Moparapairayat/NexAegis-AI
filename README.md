# NexAegis AI

Next-generation AI defense and automation for developers.

**Developer / Author:** MOPARA PAIR AYAT (Full Stack SWE · AI/ML · AML · Data Engineering)

NexAegis AI is a local-first, risk-aware AI DevOps terminal. It understands a project, scans project health, predicts engineering risk, checks security hygiene, explains errors, suggests safe fixes, helps with Git commits, and refuses to run dangerous commands without explicit human review.

## Why It Is Different

- Local-first by default: project scans and state stay on your machine.
- Zero-cost capable: the deterministic `rule_based` provider works without paid AI.
- AI optional: configure local Ollama for richer answers when you want it.
- Dry-run first: fix commands preview changes before applying anything.
- Backup-first patching: applied patches create rollback metadata under `.nexaegis/backups/`.
- Risk-aware workflow: `nax risk` highlights sensitive files, missing tests, CI gaps, dependency changes, and release hazards.
- Command firewall: `nax run` checks commands before execution and records command history.
- Automation-ready reports: `nax report` and `nax ci` support local CI gates.

## Install

```bash
uv sync
uv run nax --help
```

For editable local development:

```bash
uv pip install -e .
nax --help
```

## Quickstart

```bash
nax init
nax doctor
nax risk
nax security
nax explain "ModuleNotFoundError: No module named 'rich'"
nax run "rm -rf build" --dry-run
nax fix --dry-run
nax report --format markdown --output .nexaegis/report.md
```

## Commands

| Command | Purpose |
| --- | --- |
| `nax init` | Create `.nexaegis/config.yaml` and local SQLite state. |
| `nax doctor` | Scan project structure and save a health score. |
| `nax risk` | Score engineering risk from changed files and project gaps. |
| `nax security` | Run optional free scanners when installed plus built-in secret checks. |
| `nax explain` | Explain common errors without executing commands. |
| `nax ask` | Answer project questions from compact local context. |
| `nax run` | Risk-check and optionally run a command through the command firewall. |
| `nax fix --dry-run` | Show supported safe patch previews. |
| `nax fix list` | List currently available safe fix IDs. |
| `nax fix preview <id>` | Preview a single safe fix. |
| `nax fix apply <id>` | Apply a safe fix after confirmation and backup. |
| `nax fix rollback latest` | Restore files from rollback metadata. |
| `nax fix --apply` | Apply supported patches only after confirmation and backup. |
| `nax commit` | Suggest a commit message and only commit if config allows execution. |
| `nax ui` | Open a Textual dashboard for latest local scores. |
| `nax report` | Generate JSON or Markdown health, risk, and security reports. |
| `nax ci` | Run non-interactive local CI gates. |
| `nax history` | Show local scan, command, and fix history. |

## Safety Model

NexAegis is conservative. It never applies file changes in dry-run mode, never applies patches without confirmation, and blocks or requires confirmation for dangerous command patterns such as `rm -rf`, `sudo`, `chmod 777`, `git push --force`, `drop database`, `kubectl delete`, `terraform destroy`, namespace deletion, and `docker system prune`.

Default config:

```yaml
project_name: your-folder
safe_mode: true
ai_provider: rule_based
ollama_model: qwen2.5-coder:1.5b
risk_threshold: medium
allow_apply_patch: true
allow_command_execution: false
ci_min_health_score: 70
ci_min_security_score: 80
ci_max_risk_level: medium
risk_weights:
  not_git_repo: 18
  changed_file_base: 0
  changed_file_per_file: 3
  changed_file_cap: 18
  sensitive_base: 12
  sensitive_per_file: 4
  sensitive_cap: 30
  dependency_change: 15
  missing_tests: 20
  missing_ci: 10
  missing_dockerfile: 5
  missing_env_example: 10
```

## Zero-Cost AI Mode

The default `rule_based` provider handles common errors and project readiness questions deterministically. To use local AI, install and start Ollama, then set:

```yaml
ai_provider: ollama
ollama_model: qwen2.5-coder:1.5b
```

No paid API is required.

## Security Scanners

`nax security` uses these tools when present and reports clear install suggestions when they are missing:

- Bandit
- pip-audit
- detect-secrets
- Gitleaks

Missing optional tools do not fail the command.

Built-in checks also flag common Dockerfile, Terraform, and Kubernetes risks such as `latest` image tags, privileged containers, public Terraform exposure, and broad ingress CIDRs.

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Roadmap

- Richer risk models with language-aware file ownership signals.
- More safe fix classes and rollback commands.
- Expanded TUI workflows.
- Code Connectors for local-only LLM providers.
- SARIF export for CI integrations.

## Disclaimer

NexAegis AI is a local-first security and developer workflow tool. It can miss risks and false-positive on safe patterns. You must review all suggested commands, patches, and commit messages before use.
