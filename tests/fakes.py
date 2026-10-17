"""Test doubles."""

import json
from itertools import count

from agentco.llm import LLMResponse, ToolCall

_ids = count(1)


def tool_call(name: str, **arguments) -> ToolCall:
    return ToolCall(id=f"call_{next(_ids)}", name=name, arguments=json.dumps(arguments))


class ScriptedLLM:
    """Plays back scripted replies. Each reply is text, a ToolCall, a list of ToolCalls,
    or an Exception to raise. Records the messages it was sent."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[list[dict]] = []

    def chat(self, messages, system=None, tools=None, **options) -> LLMResponse:
        self.calls.append([dict(m) for m in messages])
        reply = self.script.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, ToolCall):
            reply = [reply]
        text, calls = (reply, []) if isinstance(reply, str) else ("", reply)
        return LLMResponse(
            text=text, model="scripted", prompt_tokens=10, completion_tokens=5,
            latency_s=0.0, tool_calls=calls,
        )
