import pytest

from agentco.tools.base import ToolContext
from agentco.tools.permissions import is_allowed, role_type, tools_for_role
from agentco.tools.toolbox import ToolBox
from agentco.tools.workspace import workspace
from agentco.workspace import service
from agentco.workspace.models import ProjectCreate


@pytest.fixture
def toolbox_for(session):
    project_id = service.create_project(session, ProjectCreate(name="P")).id
    return lambda role: ToolBox.for_role(workspace, ToolContext(session, project_id, role))


def test_role_type_strips_number():
    assert role_type("engineer_2") == "engineer"
    assert role_type("program_manager") == "program_manager"


def test_wildcards():
    assert is_allowed("board_create_ticket", ["board_*"])
    assert not is_allowed("board_create_ticket", ["board_list_tickets", "docs_*"])
    assert not is_allowed("anything", [])


def test_engineer_cannot_create_tickets_or_write_docs(toolbox_for):
    names = toolbox_for("engineer_1").names()
    assert "board_update_ticket" in names and "chat_post" in names
    assert "board_create_ticket" not in names and "docs_write" not in names


def test_pm_has_all_workspace_tools(toolbox_for):
    assert toolbox_for("pm").names() == workspace.names()


def test_only_allowed_tools_are_shown_to_the_llm(toolbox_for):
    box = toolbox_for("qa")
    assert [s["function"]["name"] for s in box.schemas()] == box.names()


def test_denied_call_explains_why(toolbox_for):
    result = toolbox_for("engineer_1").call("docs_write", {"slug": "prd", "title": "x", "content": "y"})
    assert not result.ok
    assert result.error.startswith("Permission denied: engineer_1 cannot use docs_write. Your tools: ")


def test_unknown_role_gets_no_tools(toolbox_for):
    box = toolbox_for("intern")
    assert box.names() == []
    assert "Your tools: none" in box.call("chat_post", {"channel": "general", "body": "hi"}).error
