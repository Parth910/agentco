"""Runs tool calls for one agent: parses and validates arguments, executes the tool,
and turns every failure into an error message the agent can learn from."""

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from agentco.tools.base import Registry, ToolContext, ToolError, ToolResult
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
    def __init__(self, registry: Registry, ctx: ToolContext):
        self.registry = registry
        self.ctx = ctx

    def schemas(self) -> list[dict]:
        return [self.registry.tools[name].schema() for name in self.registry.names()]

    def call(self, name: str, arguments: str | dict | None = None) -> ToolResult:
        """Run one tool call. Never raises: problems come back as ToolResult(ok=False)."""
        tool = self.registry.get(name)
        if tool is None:
            available = ", ".join(self.registry.names())
            return ToolResult(ok=False, error=f"Unknown tool '{name}'. Available tools: {available}")

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
