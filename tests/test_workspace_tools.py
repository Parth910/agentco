import pytest

from agentco.tools.base import ToolContext
from agentco.tools.toolbox import ToolBox
from agentco.tools.workspace import workspace
from agentco.workspace import service
from agentco.workspace.models import ProjectCreate


@pytest.fixture
def project_id(session):
    return service.create_project(session, ProjectCreate(name="Social feed")).id


@pytest.fixture
def as_role(session, project_id):
    """as_role("pm").call(...) runs a tool as that role."""
    return lambda role: ToolBox(workspace, ToolContext(session, project_id, role))


def test_all_tools_have_valid_schemas():
    names = workspace.names()
    assert len(names) == 11
    for name in names:
        fn = workspace.get(name).schema()["function"]
        assert fn["description"] and fn["parameters"]["type"] == "object"


def test_ticket_lifecycle(as_role):
    pm, eng = as_role("pm"), as_role("engineer_1")

    created = pm.call("board_create_ticket", {"title": "Posts API", "assignee": "engineer_1", "priority": 1})
    assert created.data == {"number": 1, "title": "Posts API", "status": "todo", "assignee": "engineer_1", "priority": 1}

    mine = eng.call("board_list_tickets", {"assignee": "me"}).data
    assert [t["number"] for t in mine] == [1]

    assert eng.call("board_update_ticket", {"number": 1, "status": "in_progress"}).data["status"] == "in_progress"
    eng.call("board_comment", {"number": 1, "body": "Endpoint done"})

    ticket = pm.call("board_get_ticket", {"number": 1}).data
    assert ticket["created_by"] == "pm"
    assert ticket["comments"] == [{"author": "engineer_1", "body": "Endpoint done"}]


def test_tools_act_as_the_caller(as_role, session, project_id):
    as_role("qa").call("chat_post", {"channel": "general", "body": "hi"})
    as_role("qa").call("docs_write", {"slug": "test-plan", "title": "Test plan", "content": "..."})
    actors = {e.actor for e in service.list_events(session, project_id) if e.type != "project_created"}
    assert actors == {"qa"}


def test_helpful_errors(as_role):
    pm = as_role("pm")
    pm.call("docs_write", {"slug": "prd", "title": "PRD", "content": "v1"})

    assert pm.call("docs_read", {"slug": "roadmap"}).error == "Doc 'roadmap' not found. Available docs: prd"
    assert pm.call("board_get_ticket", {"number": 7}).error == "Ticket 7 not found. Existing tickets: none yet"
    assert "Nothing to update" in pm.call("board_update_ticket", {"number": 1}).error
    assert "status" in pm.call("board_update_ticket", {"number": 1, "status": "blocked"}).error


def test_lenient_inputs(as_role):
    pm = as_role("pm")
    posted = pm.call("chat_post", {"channel": "#Eng", "body": "@engineer_1 start please"}).data
    assert (posted["channel"], posted["mentions"]) == ("eng", ["engineer_1"])

    pm.call("docs_write", {"slug": "Tech Design", "title": "Tech design", "content": "..."})
    assert pm.call("docs_read", {"slug": "tech-design"}).ok


def test_docs_versions(as_role):
    pm = as_role("pm")
    assert pm.call("docs_write", {"slug": "prd", "title": "PRD", "content": "v1"}).data == {"slug": "prd", "version": 1}
    assert pm.call("docs_write", {"slug": "prd", "title": "PRD", "content": "v2"}).data["version"] == 2
    assert pm.call("docs_list").data == [{"slug": "prd", "title": "PRD", "version": 2, "author": "pm"}]


def test_chat_read_and_inbox(as_role):
    pm, qa = as_role("pm"), as_role("qa")
    pm.call("chat_post", {"channel": "eng", "body": "@qa please review ticket 1"})
    pm.call("chat_post", {"channel": "general", "body": "lunch?"})

    assert [m["body"] for m in qa.call("chat_read", {"channel": "eng"}).data] == ["@qa please review ticket 1"]
    inbox = qa.call("chat_inbox").data
    assert [(m["channel"], m["author"]) for m in inbox] == [("eng", "pm")]
    assert qa.call("chat_inbox", {"after_id": inbox[0]["id"]}).data == []
