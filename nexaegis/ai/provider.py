from __future__ import annotations

from typing import Protocol

from nexaegis.core.config import NexAegisConfig


class AIProvider(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str:
        """Complete a prompt with an optional system instruction."""


def get_provider(config: NexAegisConfig) -> AIProvider:
    if config.ai_provider.lower() == "ollama":
        from nexaegis.ai.ollama import OllamaProvider

        return OllamaProvider(model=config.ollama_model)

    from nexaegis.ai.rule_based import RuleBasedProvider

    return RuleBasedProvider()
