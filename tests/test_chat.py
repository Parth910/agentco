from agentco.workspace.service import parse_mentions


def post(api, project, channel="general", author="pm", body="hello"):
    return api.post(
        f"/projects/{project['id']}/channels/{channel}/messages",
        json={"author": author, "body": body},
    )


def test_parse_mentions():
    assert parse_mentions("@pm and @qa, also @pm") == ["pm", "qa"]
    assert parse_mentions("email dev@example.com, (@qa)") == ["qa"]
    assert parse_mentions("nothing here") == []


def test_post_and_list_channel(api, project):
    post(api, project, body="kickoff")
    post(api, project, channel="eng", author="engineer_1", body="starting T-1")
    messages = api.get(f"/projects/{project['id']}/channels/general/messages").json()
    assert [m["body"] for m in messages] == ["kickoff"]
    assert api.get(f"/projects/{project['id']}/channels").json() == ["eng", "general"]


def test_mentions_detected_and_inbox(api, project):
    msg = post(api, project, body="@engineer_1 please pick T-1, cc @qa").json()
    assert msg["mentions"] == ["engineer_1", "qa"]
    post(api, project, channel="eng", body="@qa ready for review")
    post(api, project, body="no mention")

    inbox = api.get(f"/projects/{project['id']}/messages?mention=qa").json()
    assert [m["channel"] for m in inbox] == ["general", "eng"]


def test_polling_with_after_id(api, project):
    first = post(api, project, body="one").json()
    post(api, project, body="two")
    post(api, project, body="three")
    newer = api.get(f"/projects/{project['id']}/messages?after_id={first['id']}&limit=1").json()
    assert [m["body"] for m in newer] == ["two"]


def test_limit_returns_latest_oldest_first(api, project):
    for body in ["one", "two", "three"]:
        post(api, project, body=body)
    latest = api.get(f"/projects/{project['id']}/channels/general/messages?limit=2").json()
    assert [m["body"] for m in latest] == ["two", "three"]


def test_invalid_channel_and_empty_body(api, project):
    assert post(api, project, channel="Bad Channel").status_code == 400
    assert post(api, project, body="").status_code == 422
