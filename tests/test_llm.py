"""LLM client tests against a fake OpenAI-compatible server (no real model needed)."""

import json

import httpx
import pytest
from pydantic import BaseModel

from agentco.llm import LLMClient, LLMConfig, StructuredOutputError
from agentco.llm.client import extract_json


class Idea(BaseModel):
    name: str
    features: list[str]


class FakeLLM:
    """Returns the given replies in order and records every request body."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.requests: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "fake-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": self.replies.pop(0)},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    def client(self, **config) -> LLMClient:
        cfg = LLMConfig(base_url="http://fake/v1", model="fake-model", **config)
        return LLMClient(cfg, http_client=httpx.Client(transport=httpx.MockTransport(self.handler)))


# --- config ------------------------------------------------------------------

def test_config_defaults(monkeypatch):
    for key in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_REASONING_EFFORT"):
        monkeypatch.delenv(key, raising=False)
    cfg = LLMConfig.from_env()
    assert cfg.model == "qwen3:8b"
    assert cfg.reasoning_effort == "none"


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "other")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
    cfg = LLMConfig.from_env()
    assert (cfg.model, cfg.reasoning_effort, cfg.temperature) == ("other", "", 0.7)


# --- chat --------------------------------------------------------------------

def test_chat_returns_text_and_usage():
    fake = FakeLLM("hello")
    r = fake.client().chat("hi", system="be brief")

    assert r.text == "hello"
    assert (r.prompt_tokens, r.completion_tokens) == (10, 5)
    sent = fake.requests[0]
    assert sent["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
    ]
    assert sent["model"] == "fake-model"
    assert sent["reasoning_effort"] == "none"


def test_chat_omits_reasoning_effort_when_empty():
    fake = FakeLLM("hello")
    fake.client(reasoning_effort="").chat("hi")
    assert "reasoning_effort" not in fake.requests[0]


# --- structured --------------------------------------------------------------

def test_structured_valid_first_try():
    fake = FakeLLM('{"name": "CampusLoop", "features": ["feed", "likes"]}')
    s = fake.client().structured("idea please", Idea)

    assert s.data == Idea(name="CampusLoop", features=["feed", "likes"])
    assert s.attempts == 1
    assert fake.requests[0]["response_format"]["json_schema"]["name"] == "Idea"


def test_structured_retries_with_error_feedback():
    fake = FakeLLM('{"name": "CampusLoop"}', '{"name": "CampusLoop", "features": ["feed"]}')
    s = fake.client().structured("idea please", Idea)

    assert s.attempts == 2
    retry_messages = fake.requests[1]["messages"]
    assert retry_messages[-2] == {"role": "assistant", "content": '{"name": "CampusLoop"}'}
    assert "features" in retry_messages[-1]["content"]


def test_structured_gives_up_after_max_retries():
    fake = FakeLLM("not json", "still not", "nope")
    with pytest.raises(StructuredOutputError):
        fake.client().structured("idea please", Idea, max_retries=2)
    assert len(fake.requests) == 3


def test_extract_json_strips_code_fences():
    assert extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert extract_json('  {"a": 1} ') == '{"a": 1}'
