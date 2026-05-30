from nexaegis.core.policies import CommandRule, load_custom_policy_file
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
