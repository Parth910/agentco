"""Client for any OpenAI-compatible chat API (Ollama by default)."""

import time
from dataclasses import dataclass

from openai import OpenAI

from agentco.llm.config import LLMConfig

Messages = list[dict[str, str]]


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float


def build_messages(prompt: str | Messages, system: str | None = None) -> Messages:
    """Accept a plain string or a full message list; prepend a system prompt if given."""
    messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else list(prompt)
    if system:
        messages.insert(0, {"role": "system", "content": system})
    return messages


class LLMClient:
    def __init__(self, config: LLMConfig | None = None, http_client=None):
        self.config = config or LLMConfig.from_env()
        # http_client lets tests swap in a fake transport.
        self._openai = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=self.config.timeout,
            http_client=http_client,
        )

    def _request_options(self) -> dict:
        options = {"model": self.config.model, "temperature": self.config.temperature}
        if self.config.reasoning_effort:
            options["reasoning_effort"] = self.config.reasoning_effort
        return options

    def chat(self, prompt: str | Messages, system: str | None = None, **options) -> LLMResponse:
        """Send messages, return the assistant's reply with token usage and latency."""
        started = time.perf_counter()
        completion = self._openai.chat.completions.create(
            messages=build_messages(prompt, system),
            **{**self._request_options(), **options},
        )
        latency = time.perf_counter() - started

        usage = completion.usage
        return LLMResponse(
            text=completion.choices[0].message.content or "",
            model=completion.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            latency_s=round(latency, 3),
        )
