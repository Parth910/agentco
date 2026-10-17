"""Tool basics: what a tool is and how it is described to the LLM.

A tool is a function `fn(ctx, args)` where `args` is a Pydantic model. The function
name becomes the tool name, its docstring the description, and the args model the
JSON schema the LLM fills in.
"""

import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, get_type_hints

from pydantic import BaseModel
from sqlmodel import Session


@dataclass
class ToolContext:
    session: Session
    project_id: int
    actor: str  # the role calling the tool; tools act as this role


class ToolError(Exception):
    """A problem the agent can fix (bad input, missing item). The message is sent back to it."""


@dataclass
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    fn: Callable[[ToolContext, Any], Any]

    def schema(self) -> dict:
        """The tool in OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args.model_json_schema(),
            },
        }


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: str | None = None

    def to_content(self) -> str:
        """What the agent sees as the tool's reply."""
        body = {"ok": True, "result": self.data} if self.ok else {"ok": False, "error": self.error}
        return json.dumps(body, default=str)


class Registry:
    """A named set of tools. Register with the @registry.tool decorator."""

    def __init__(self) -> None:
        self.tools: dict[str, Tool] = {}

    def tool(self, fn: Callable) -> Callable:
        args_model = get_type_hints(fn).get("args")
        if not (inspect.isclass(args_model) and issubclass(args_model, BaseModel)):
            raise TypeError(f"Tool {fn.__name__} needs an `args: <PydanticModel>` parameter")
        description = inspect.getdoc(fn)
        if not description:
            raise TypeError(f"Tool {fn.__name__} needs a docstring (it is the LLM's description)")
        self.tools[fn.__name__] = Tool(fn.__name__, description, args_model, fn)
        return fn

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def names(self) -> list[str]:
        return list(self.tools)
