from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class OllamaProvider:
    model: str
    endpoint: str = "http://localhost:11434/api/generate"
    timeout: int = 30

    def complete(self, prompt: str, system: str | None = None) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system or "",
            "stream": False,
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return (
                "Ollama is configured but unavailable. Start Ollama locally or switch "
                f"`ai_provider` to `rule_based`. Details: {exc}"
            )
        return str(data.get("response", "")).strip() or "Ollama returned an empty response."
