def new_ticket(api, project, **fields):
    body = {"title": "Create posts API", **fields}
    return api.post(f"/projects/{project['id']}/tickets", json=body)


def test_tickets_are_numbered_per_project(api, project):
    other = api.post("/projects", json={"name": "Other"}).json()
    assert new_ticket(api, project).json()["number"] == 1
    assert new_ticket(api, project).json()["number"] == 2
    assert new_ticket(api, other).json()["number"] == 1


def test_new_ticket_defaults(api, project):
    ticket = new_ticket(api, project).json()
    assert ticket["status"] == "todo"
    assert ticket["priority"] == 2
    assert ticket["assignee"] is None
    assert ticket["created_by"] == "ceo"


def test_move_and_assign_ticket(api, project):
    new_ticket(api, project)
    url = f"/projects/{project['id']}/tickets/1"

    moved = api.patch(url, json={"status": "in_progress", "assignee": "engineer_1"}).json()
    assert (moved["status"], moved["assignee"]) == ("in_progress", "engineer_1")

    unassigned = api.patch(url, json={"assignee": None}).json()
    assert unassigned["assignee"] is None
    assert unassigned["status"] == "in_progress"  # untouched


def test_null_for_required_field_is_ignored(api, project):
    new_ticket(api, project)
    ticket = api.patch(f"/projects/{project['id']}/tickets/1", json={"title": None}).json()
    assert ticket["title"] == "Create posts API"


def test_invalid_status_and_priority_rejected(api, project):
    new_ticket(api, project)
    url = f"/projects/{project['id']}/tickets/1"
    assert api.patch(url, json={"status": "blocked"}).status_code == 422
    assert new_ticket(api, project, priority=5).status_code == 422


def test_filter_tickets(api, project):
    new_ticket(api, project, assignee="engineer_1")
    new_ticket(api, project, assignee="qa")
    api.patch(f"/projects/{project['id']}/tickets/2", json={"status": "review"})
    base = f"/projects/{project['id']}/tickets"

    assert [t["number"] for t in api.get(base).json()] == [1, 2]
    assert [t["number"] for t in api.get(f"{base}?assignee=qa").json()] == [2]
    assert [t["number"] for t in api.get(f"{base}?status=todo").json()] == [1]


def test_comments(api, project):
    new_ticket(api, project)
    url = f"/projects/{project['id']}/tickets/1/comments"
    api.post(url, json={"author": "qa", "body": "2 tests failing"})
    api.post(url, json={"author": "engineer_1", "body": "Fixed"})
    assert [c["author"] for c in api.get(url).json()] == ["qa", "engineer_1"]


def test_missing_ticket_and_project_are_404(api, project):
    assert api.get(f"/projects/{project['id']}/tickets/9").status_code == 404
    assert new_ticket(api, {"id": 99}).status_code == 404
