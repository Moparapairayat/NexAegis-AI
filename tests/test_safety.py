import pytest
import typer

from nexaegis.cli.commands.run import run_checked_command
from nexaegis.core.config import default_config, write_default_config
from nexaegis.core.context import get_project_context
from nexaegis.core.policies import (
    CommandRule,
    PolicyError,
    load_command_rules,
    load_custom_policy_file,
)
from nexaegis.core.safety import evaluate_command


def test_blocks_recursive_delete_in_safe_mode() -> None:
    result = evaluate_command("rm -rf ./build", safe_mode=True)

    assert result.allowed is False
    assert result.requires_confirmation is True
    assert result.safer_alternative is not None


def test_allows_normal_test_command() -> None:
    result = evaluate_command("uv run pytest", safe_mode=True)

    assert result.allowed is True
    assert result.requires_confirmation is False


def test_detects_force_push() -> None:
    result = evaluate_command("git push origin main --force", safe_mode=True)

    assert result.allowed is False
    assert "history" in result.reason


def test_classifies_normal_command() -> None:
    result = evaluate_command("uv run pytest", safe_mode=True)

    assert result.category == "python"
    assert result.risk_score == 0


def test_custom_policy_can_block_command(tmp_path) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "command_rules:",
                "  - name: block_echo",
                "    pattern: '^echo secret'",
                "    reason: 'Secret echo is not allowed.'",
                "    action: block",
                "    category: secrets",
                "    risk_score: 80",
            ]
        ),
        encoding="utf-8",
    )

    rules = load_custom_policy_file(policy)
    result = evaluate_command("echo secret", safe_mode=True, rules=rules)

    assert isinstance(rules[0], CommandRule)
    assert result.allowed is False
    assert result.requires_confirmation is False
    assert result.category == "secrets"


def test_unknown_policy_pack_fails_closed(tmp_path) -> None:
    config = default_config(tmp_path)
    config.policy_packs = ["missing-pack"]

    with pytest.raises(PolicyError):
        load_command_rules(config, tmp_path)


def test_detects_windows_recursive_delete() -> None:
    result = evaluate_command("Remove-Item build -Recurse -Force", safe_mode=True)

    assert result.allowed is False
    assert result.requires_confirmation is True
    assert result.category == "filesystem"


def test_block_policy_cannot_be_overridden_with_execute_yes(tmp_path) -> None:
    write_default_config(tmp_path)
    policy = tmp_path / ".nexaegis" / "policy.yaml"
    policy.write_text(
        "\n".join(
            [
                "command_rules:",
                "  - name: block_python",
                "    pattern: '^python'",
                "    reason: 'Python execution is blocked for this test.'",
                "    action: block",
                "    category: test",
            ]
        ),
        encoding="utf-8",
    )
    config_file = tmp_path / ".nexaegis" / "config.yaml"
    config_file.write_text(
        config_file.read_text(encoding="utf-8")
        + "\nallow_command_execution: true\ncustom_policy_paths:\n  - .nexaegis/policy.yaml\n",
        encoding="utf-8",
    )
    context = get_project_context(tmp_path)

    with pytest.raises(typer.Exit):
        run_checked_command(
            context,
            "python -c \"open('marker.txt', 'w').write('ran')\"",
            execute=True,
            yes=True,
        )

    assert not (tmp_path / "marker.txt").exists()
