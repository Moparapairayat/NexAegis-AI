# Safety Model

NexAegis AI is designed around reversible, local-first operation.

## Defaults

- `safe_mode: true`
- `ai_provider: rule_based`
- `allow_apply_patch: true`
- `allow_command_execution: false`
- `ci_max_risk_level: medium`

## Command Safety

The dangerous command detector identifies high-risk patterns:

- `rm -rf`
- `sudo`
- `chmod 777`
- `git push --force`
- `drop database`
- `kubectl delete`
- `terraform destroy`
- `delete namespace`
- `docker system prune`

When safe mode is enabled, these commands are not allowed automatically and require explicit review.

`nax run` is the command firewall. It prints a structured verdict before execution. With default config it will not run commands unless the user passes `--execute`; dangerous commands also require confirmation or explicit danger acknowledgement.

## Patch Safety

`nax fix --dry-run` and `nax fix preview <id>` only render diff-like previews. `nax fix --apply` and `nax fix apply <id>` first show affected files, risk level, and backup location, then ask for confirmation. Applied patches create backups and rollback metadata under `.nexaegis/backups/`. `nax fix rollback latest` restores the latest backed-up batch after confirmation.

## CI Safety

`nax ci` is non-interactive. It runs local doctor, risk, and security checks, records the results, and exits non-zero when configured gates fail.

## AI Safety

AI is optional. The default rule-based provider avoids network access and handles common project questions. Ollama runs locally when configured. NexAegis does not send full codebases by default; `nax ask` builds a compact context from metadata and excerpts.
