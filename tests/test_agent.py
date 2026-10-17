import json

import pytest

from agentco.agents.base import Agent
from agentco.tools.base import ToolContext
from agentco.tools.toolbox import ToolBox
from agentco.tools.workspace import workspace
from agentco.workspace import service
from agentco.workspace.models import ProjectCreate
from tests.fakes import ScriptedLLM, tool_call


@pytest.fixture
def make_agent(session):
    project_id = service.create_project(session, ProjectCreate(name="P")).id

    def make(llm, role="pm", **kwargs):
        box = ToolBox.for_role(workspace, ToolContext(session, project_id, role))
        return Agent(role, "You are a PM.", llm, box, **kwargs)

    make.project_id = project_id
    return make


def test_loops_through_tools_until_it_answers(make_agent, session):
    llm = ScriptedLLM(
        tool_call("board_create_ticket", title="Posts API"),
        [tool_call("board_create_ticket", title="Likes"), tool_call("chat_post", channel="eng", body="go")],
        "Created 2 tickets and told the team.",
    )
    run = make_agent(llm).run("Plan the work")

    assert run.stop_reason == "done"
    assert run.final_text == "Created 2 tickets and told the team."
    assert (run.steps, run.tool_calls) == (3, 3)
    assert (run.prompt_tokens, run.completion_tokens) == (30, 15)
    tickets = service.list_tickets(session, make_agent.project_id)
    assert [t.title for t in tickets] == ["Posts API", "Likes"]


def test_tool_results_are_fed_back(make_agent):
    llm = ScriptedLLM(tool_call("docs_read", slug="prd"), "No PRD yet.")
    make_agent(llm).run("Read the PRD")

    second_request = llm.calls[1]
    assistant, tool_reply = second_request[-2], second_request[-1]
    assert assistant["tool_calls"][0]["function"]["name"] == "docs_read"
    assert tool_reply["role"] == "tool"
    assert tool_reply["tool_call_id"] == assistant["tool_calls"][0]["id"]
    assert json.loads(tool_reply["content"])["ok"] is False  # errors are fed back too


def test_stops_at_max_steps(make_agent):
    llm = ScriptedLLM(*[tool_call("board_list_tickets")] * 5)
    run = make_agent(llm, max_steps=3).run("Loop forever")
    assert (run.stop_reason, run.steps, run.tool_calls) == ("max_steps", 3, 3)


def test_llm_failure_stops_cleanly(make_agent):
    run = make_agent(ScriptedLLM(ConnectionError("Ollama down"))).run("Anything")
    assert run.stop_reason == "llm_error"
    assert "Ollama down" in run.final_text


def test_progress_events(make_agent):
    seen = []
    llm = ScriptedLLM(tool_call("board_list_tickets"), "Board is empty.")
    make_agent(llm, on_event=lambda kind, data: seen.append(kind)).run("Check the board")
    assert seen == ["tool", "message"]
