"""OpenAI-compatible LLM client (Ollama by default)."""

from agentco.llm.client import (
    LLMClient,
    LLMResponse,
    StructuredOutputError,
    StructuredResponse,
)
from agentco.llm.config import LLMConfig

__all__ = [
    "LLMClient",
    "LLMConfig",
    "LLMResponse",
    "StructuredOutputError",
    "StructuredResponse",
]
