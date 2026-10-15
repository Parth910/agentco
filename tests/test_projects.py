def test_create_and_get_project(api):
    created = api.post("/projects", json={"name": "Social feed", "idea": "Feed for students"})
    assert created.status_code == 201
    project = created.json()
    assert project["id"] == 1
    assert api.get("/projects/1").json()["name"] == "Social feed"


def test_list_projects_newest_first(api):
    api.post("/projects", json={"name": "First"})
    api.post("/projects", json={"name": "Second"})
    assert [p["name"] for p in api.get("/projects").json()] == ["Second", "First"]


def test_project_name_required(api):
    assert api.post("/projects", json={"name": ""}).status_code == 422


def test_missing_project_is_404(api):
    response = api.get("/projects/99")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project 99 not found"
