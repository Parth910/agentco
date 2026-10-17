def events(api, project, query=""):
    return api.get(f"/projects/{project['id']}/events{query}").json()


def test_every_change_is_logged_with_actor(api, project):
    pid = project["id"]
    api.post(f"/projects/{pid}/tickets", json={"title": "Posts API", "created_by": "pm"})
    api.patch(f"/projects/{pid}/tickets/1", json={"status": "in_progress"}, headers={"X-Actor": "engineer_1"})
    api.post(f"/projects/{pid}/tickets/1/comments", json={"author": "qa", "body": "ok"})
    api.put(f"/projects/{pid}/docs/prd", json={"title": "PRD", "author": "pm"})
    api.post(f"/projects/{pid}/channels/eng/messages", json={"author": "pm", "body": "@qa hi"})

    timeline = [(e["actor"], e["type"]) for e in events(api, project)]
    assert timeline == [
        ("ceo", "project_created"),
        ("pm", "ticket_created"),
        ("engineer_1", "ticket_updated"),
        ("qa", "comment_added"),
        ("pm", "doc_written"),
        ("pm", "message_posted"),
    ]


def test_event_data(api, project):
    pid = project["id"]
    api.post(f"/projects/{pid}/tickets", json={"title": "Posts API"})
    api.patch(f"/projects/{pid}/tickets/1", json={"status": "review"})
    api.post(f"/projects/{pid}/channels/eng/messages", json={"author": "pm", "body": "@qa look"})

    updated = events(api, project, "?type=ticket_updated")[0]
    assert updated["data"] == {"number": 1, "changes": {"status": "review"}}
    posted = events(api, project, "?type=message_posted")[0]
    assert posted["data"]["mentions"] == ["qa"]


def test_unchanged_updates_are_not_logged(api, project):
    pid = project["id"]
    api.put(f"/projects/{pid}/docs/prd", json={"title": "PRD", "author": "pm"})
    api.put(f"/projects/{pid}/docs/prd", json={"title": "PRD", "author": "pm"})
    api.post(f"/projects/{pid}/tickets", json={"title": "Posts API"})
    api.patch(f"/projects/{pid}/tickets/1", json={})
    assert len(events(api, project, "?type=doc_written")) == 1
    assert events(api, project, "?type=ticket_updated") == []


def test_filter_and_poll_events(api, project):
    pid = project["id"]
    api.post(f"/projects/{pid}/tickets", json={"title": "A", "created_by": "pm"})
    api.post(f"/projects/{pid}/tickets", json={"title": "B", "created_by": "qa"})
    assert [e["actor"] for e in events(api, project, "?actor=qa")] == ["qa"]

    first = events(api, project)[0]["id"]
    newer = events(api, project, f"?after_id={first}&limit=1")
    assert [e["type"] for e in newer] == ["ticket_created"]
    assert newer[0]["data"]["title"] == "A"
