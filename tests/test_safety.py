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
