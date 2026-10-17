import pytest

from agentco.agents.roles import PM, make_agent, pm_check_done, task_for_idea
from agentco.tools.base import ToolContext
from agentco.workspace import service
from agentco.workspace.models import DocWrite, MessageCreate, ProjectCreate, TicketCreate
from tests.fakes import ScriptedLLM, tool_call


@pytest.fixture
def ctx(session):
    project_id = service.create_project(session, ProjectCreate(name="P")).id
    return ToolContext(session, project_id, "pm")


def test_pm_check_lists_everything_missing(ctx):
    missing = pm_check_done(ctx)
    assert 'docs_write (slug "prd")' in missing
    assert "only 0 tickets" in missing
    assert "kickoff" in missing


def test_pm_check_passes_when_work_is_complete(ctx):
    service.write_doc(ctx.session, ctx.project_id, "prd", DocWrite(title="PRD", author="pm"))
    for i in range(4):
        service.create_ticket(ctx.session, ctx.project_id, TicketCreate(title=f"T{i}"))
    service.post_message(ctx.session, ctx.project_id, "general", MessageCreate(author="pm", body="kickoff"))
    assert pm_check_done(ctx) is None


def test_pm_agent_end_to_end_with_nudge(ctx):
    tickets = [tool_call("board_create_ticket", title=f"T{i}", assignee="engineer_1") for i in range(3)]
    llm = ScriptedLLM(
        [tool_call("docs_write", slug="prd", title="PRD: Feed", content="..."), *tickets],
        tool_call("chat_post", channel="general", body="Kickoff @engineer_1 @qa"),
        "Planned it.",  # only 3 tickets: gets nudged
        tool_call("board_create_ticket", title="T3", assignee="engineer_1"),
        "Planned it, 4 tickets.",
    )
    run = make_agent(PM, ctx.session, ctx.project_id, llm).run(task_for_idea("A social feed"))

    assert (run.stop_reason, run.nudges) == ("done", 1)
    assert "only 3 tickets" in llm.calls[3][-1]["content"]
    assert len(service.list_tickets(ctx.session, ctx.project_id)) == 4
