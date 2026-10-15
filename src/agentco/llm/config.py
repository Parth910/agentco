"""LLM settings, read from environment variables (see .env.example)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = "http://host.docker.internal:11434/v1"
    model: str = "qwen3:8b"
    # Ollama ignores the key, but the OpenAI SDK requires a non-empty value.
    api_key: str = "ollama"
    # "none" turns off thinking on reasoning models like qwen3: much faster.
    # Empty string means "don't send it" (for providers that reject the field).
    reasoning_effort: str = "none"
    temperature: float = 0.2
    timeout: float = 300.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        defaults = cls()
        return cls(
            base_url=os.getenv("LLM_BASE_URL") or defaults.base_url,
            model=os.getenv("LLM_MODEL") or defaults.model,
            api_key=os.getenv("LLM_API_KEY") or defaults.api_key,
            reasoning_effort=os.getenv("LLM_REASONING_EFFORT", defaults.reasoning_effort),
            temperature=float(os.getenv("LLM_TEMPERATURE") or defaults.temperature),
            timeout=float(os.getenv("LLM_TIMEOUT") or defaults.timeout),
        )
