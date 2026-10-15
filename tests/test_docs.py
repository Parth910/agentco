def write(api, project, slug="prd", **fields):
    body = {"title": "PRD", "content": "v1", "author": "pm", **fields}
    return api.put(f"/projects/{project['id']}/docs/{slug}", json=body)


def test_create_doc(api, project):
    doc = write(api, project).json()
    assert (doc["slug"], doc["version"], doc["author"]) == ("prd", 1, "pm")
    assert api.get(f"/projects/{project['id']}/docs/prd").json()["content"] == "v1"


def test_update_creates_new_version(api, project):
    write(api, project)
    doc = write(api, project, content="v2", author="ceo").json()
    assert (doc["version"], doc["content"], doc["author"]) == (2, "v2", "ceo")

    versions = api.get(f"/projects/{project['id']}/docs/prd/versions").json()
    assert [(v["version"], v["content"], v["author"]) for v in versions] == [
        (1, "v1", "pm"),
        (2, "v2", "ceo"),
    ]
    old = api.get(f"/projects/{project['id']}/docs/prd/versions/1").json()
    assert old["content"] == "v1"


def test_unchanged_write_adds_no_version(api, project):
    write(api, project)
    assert write(api, project).json()["version"] == 1
    assert len(api.get(f"/projects/{project['id']}/docs/prd/versions").json()) == 1


def test_list_docs(api, project):
    write(api, project, slug="research", title="Research")
    write(api, project, slug="prd")
    assert [d["slug"] for d in api.get(f"/projects/{project['id']}/docs").json()] == [
        "prd",
        "research",
    ]


def test_invalid_slug_rejected(api, project):
    response = write(api, project, slug="My PRD!")
    assert response.status_code == 400
    assert "Invalid doc slug" in response.json()["detail"]


def test_missing_doc_and_version_are_404(api, project):
    assert api.get(f"/projects/{project['id']}/docs/nope").status_code == 404
    write(api, project)
    assert api.get(f"/projects/{project['id']}/docs/prd/versions/5").status_code == 404
