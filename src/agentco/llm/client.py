"""Client for any OpenAI-compatible chat API (Ollama by default)."""

import re
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from agentco.llm.config import LLMConfig

Messages = list[dict[str, str]]
T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """The model did not return valid JSON for the schema after all retries."""


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float


@dataclass
class StructuredResponse(Generic[T]):
    data: T
    response: LLMResponse  # the final, successful call
    attempts: int


def extract_json(text: str) -> str:
    """Strip ```json fences some models wrap around JSON."""
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1) if match else text.strip()


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

    def structured(
        self,
        prompt: str | Messages,
        schema: type[T],
        system: str | None = None,
        max_retries: int = 2,
    ) -> StructuredResponse[T]:
        """Ask for JSON matching a Pydantic model; validate it and retry on errors.

        On a bad reply, the reply and the validation error are sent back so the
        model can correct itself.
        """
        messages = build_messages(prompt, system)
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
        }

        for attempt in range(1, max_retries + 2):
            response = self.chat(messages, response_format=response_format)
            try:
                data = schema.model_validate_json(extract_json(response.text))
                return StructuredResponse(data=data, response=response, attempts=attempt)
            except ValidationError as exc:
                error = exc
                messages = messages + [
                    {"role": "assistant", "content": response.text},
                    {
                        "role": "user",
                        "content": "Your reply did not match the required JSON schema:\n"
                        f"{exc}\nReply again with only valid JSON.",
                    },
                ]

        raise StructuredOutputError(
            f"No valid {schema.__name__} after {max_retries + 1} attempts: {error}"
        )
