"""Runs tool calls for one agent: checks permissions, parses and validates arguments,
executes the tool, and turns every failure into an error message the agent can learn from."""

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from agentco.tools.base import Registry, ToolContext, ToolError, ToolResult
from agentco.tools.permissions import is_allowed, tools_for_role
from agentco.workspace.service import InvalidError, NotFoundError


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    return value


def format_validation_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        where = ".".join(str(p) for p in err["loc"]) or "arguments"
        parts.append(f"{where}: {err['msg']}")
    return "Invalid arguments: " + "; ".join(parts)


class ToolBox:
    def __init__(self, registry: Registry, ctx: ToolContext, allowed: list[str] | None = None):
        """allowed: tool name patterns this agent may use (None = all tools)."""
        self.registry = registry
        self.ctx = ctx
        self.allowed = ["*"] if allowed is None else allowed

    @classmethod
    def for_role(cls, registry: Registry, ctx: ToolContext) -> "ToolBox":
        """A toolbox limited to the default tools of ctx.actor's role."""
        return cls(registry, ctx, tools_for_role(ctx.actor))

    def names(self) -> list[str]:
        """Tools this agent may use. Only these are shown to the LLM."""
        return [name for name in self.registry.names() if is_allowed(name, self.allowed)]

    def schemas(self) -> list[dict]:
        return [self.registry.tools[name].schema() for name in self.names()]

    def call(self, name: str, arguments: str | dict | None = None) -> ToolResult:
        """Run one tool call. Never raises: problems come back as ToolResult(ok=False)."""
        tool = self.registry.get(name)
        if tool is None:
            available = ", ".join(self.names())
            return ToolResult(ok=False, error=f"Unknown tool '{name}'. Available tools: {available}")
        if not is_allowed(name, self.allowed):
            yours = ", ".join(self.names()) or "none"
            return ToolResult(
                ok=False,
                error=f"Permission denied: {self.ctx.actor} cannot use {name}. Your tools: {yours}",
            )

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as exc:
                return ToolResult(ok=False, error=f"Arguments are not valid JSON: {exc}")

        try:
            args = tool.args.model_validate(arguments or {})
        except ValidationError as exc:
            return ToolResult(ok=False, error=format_validation_error(exc))

        try:
            return ToolResult(ok=True, data=to_jsonable(tool.fn(self.ctx, args)))
        except (ToolError, NotFoundError, InvalidError) as exc:
            self.ctx.session.rollback()
            return ToolResult(ok=False, error=str(exc))
        except Exception as exc:  # a bug in a tool must not crash the agent loop
            self.ctx.session.rollback()
            return ToolResult(ok=False, error=f"Tool failed: {type(exc).__name__}: {exc}")
