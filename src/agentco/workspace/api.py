"""HTTP API for the workspace. Thin layer over service.py."""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from agentco.workspace import service
from agentco.workspace.models import Project, ProjectCreate

router = APIRouter(prefix="/projects")


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


SessionDep = Depends(get_session)


# --- projects ----------------------------------------------------------------

@router.post("", status_code=201, tags=["projects"])
def create_project(data: ProjectCreate, session: Session = SessionDep) -> Project:
    return service.create_project(session, data)


@router.get("", tags=["projects"])
def list_projects(session: Session = SessionDep) -> list[Project]:
    return service.list_projects(session)


@router.get("/{project_id}", tags=["projects"])
def get_project(project_id: int, session: Session = SessionDep) -> Project:
    return service.get_project(session, project_id)
