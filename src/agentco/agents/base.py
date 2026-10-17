"""The agent loop.

Ask the LLM; if it calls tools, run them and add the results to the conversation;
repeat. The agent is done when it replies without calling a tool. A step limit
guarantees it can never loop forever.

Each run is logged as events: agent_started, agent_message, agent_finished
(tool calls are logged by the ToolBox as tool_called).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from agentco.llm import LLMClient
from agentco.tools.toolbox import ToolBox
from agentco.workspace.service import log_event

# on_event(kind, data): lets a caller show progress, e.g. ("tool", {...}).
EventCallback = Callable[[str, dict], None]


@dataclass
class AgentRun:
    role: str
    final_text: str
    stop_reason: str  # "done" | "max_steps" | "llm_error"
    steps: int = 0
    tool_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_s: float = 0.0
    messages: list[dict] = field(default_factory=list)


class Agent:
    def __init__(
        self,
        role: str,
        system_prompt: str,
        llm: LLMClient,
        toolbox: ToolBox,
        max_steps: int = 20,
        on_event: EventCallback | None = None,
    ):
        self.role = role
        self.system_prompt = system_prompt
        self.llm = llm
        self.toolbox = toolbox
        self.max_steps = max_steps
        self.on_event = on_event or (lambda kind, data: None)

    def run(self, task: str) -> AgentRun:
        started = time.perf_counter()
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]
        run = AgentRun(role=self.role, final_text="", stop_reason="max_steps", messages=messages)
        self._log("agent_started", task=task, max_steps=self.max_steps)

        while run.steps < self.max_steps:
            run.steps += 1
            try:
                reply = self.llm.chat(messages, tools=self.toolbox.schemas())
            except Exception as exc:
                run.stop_reason = "llm_error"
                run.final_text = f"LLM call failed: {exc}"
                self.on_event("error", {"step": run.steps, "error": run.final_text})
                break

            run.prompt_tokens += reply.prompt_tokens
            run.completion_tokens += reply.completion_tokens
            messages.append(reply.assistant_message())
            if reply.text.strip():
                self.on_event("message", {"step": run.steps, "text": reply.text.strip()})
                self._log("agent_message", step=run.steps, text=reply.text.strip())

            if not reply.tool_calls:
                run.stop_reason = "done"
                run.final_text = reply.text.strip()
                break

            for call in reply.tool_calls:
                result = self.toolbox.call(call.name, call.arguments)
                run.tool_calls += 1
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result.to_content()}
                )
                self.on_event(
                    "tool",
                    {
                        "step": run.steps,
                        "name": call.name,
                        "arguments": call.arguments,
                        "ok": result.ok,
                        "result": result.data if result.ok else result.error,
                    },
                )

        run.duration_s = round(time.perf_counter() - started, 2)
        self._log(
            "agent_finished",
            stop_reason=run.stop_reason,
            steps=run.steps,
            tool_calls=run.tool_calls,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            duration_s=run.duration_s,
            final_text=run.final_text[:1000],
        )
        return run

    def _log(self, type: str, **data) -> None:
        ctx = self.toolbox.ctx
        try:
            log_event(ctx.session, ctx.project_id, self.role, type, **data)
            ctx.session.commit()
        except Exception:  # logging must never break the agent
            ctx.session.rollback()
