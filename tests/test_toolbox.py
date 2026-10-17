import json

import pytest
from pydantic import BaseModel, Field

from agentco.tools.base import Registry, ToolContext, ToolError
from agentco.tools.toolbox import ToolBox

registry = Registry()


class AddArgs(BaseModel):
    a: int = Field(description="First number")
    b: int = 0


@registry.tool
def add(ctx: ToolContext, args: AddArgs) -> dict:
    """Add two numbers."""
    return {"sum": args.a + args.b, "by": ctx.actor}


class NoArgs(BaseModel):
    pass


@registry.tool
def refuse(ctx: ToolContext, args: NoArgs) -> None:
    """Always fails with a fixable error."""
    raise ToolError("Not allowed today, try tomorrow")


@registry.tool
def crash(ctx: ToolContext, args: NoArgs) -> None:
    """Has a bug."""
    raise RuntimeError("boom")


@pytest.fixture
def box(session):
    return ToolBox(registry, ToolContext(session=session, project_id=1, actor="pm"))


def test_schema_from_function():
    schema = registry.get("add").schema()
    assert schema["type"] == "function"
    fn = schema["function"]
    assert (fn["name"], fn["description"]) == ("add", "Add two numbers.")
    assert fn["parameters"]["required"] == ["a"]
    assert fn["parameters"]["properties"]["a"]["description"] == "First number"


def test_registry_requires_args_model_and_docstring():
    with pytest.raises(TypeError, match="args"):
        Registry().tool(lambda ctx, x: None)

    def no_doc(ctx: ToolContext, args: NoArgs):
        pass

    with pytest.raises(TypeError, match="docstring"):
        Registry().tool(no_doc)


def test_call_with_json_string_or_dict(box):
    assert box.call("add", '{"a": 2, "b": 3}').data == {"sum": 5, "by": "pm"}
    assert box.call("add", {"a": 2}).data == {"sum": 2, "by": "pm"}


def test_errors_come_back_as_results(box):
    unknown = box.call("multiply", "{}")
    assert not unknown.ok and "Available tools: add" in unknown.error

    assert "not valid JSON" in box.call("add", "{a: 2").error
    assert box.call("add", {"b": 1}).error == "Invalid arguments: a: Field required"
    assert box.call("refuse").error == "Not allowed today, try tomorrow"
    assert box.call("crash").error == "Tool failed: RuntimeError: boom"


def test_result_content_is_json(box):
    assert json.loads(box.call("add", {"a": 1}).to_content()) == {
        "ok": True,
        "result": {"sum": 1, "by": "pm"},
    }
    assert json.loads(box.call("refuse").to_content())["ok"] is False
