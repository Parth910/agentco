"""HTTP API for the workspace. Thin layer over service.py."""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from agentco.workspace import service
from agentco.workspace.models import (
    Comment,
    CommentCreate,
    Project,
    ProjectCreate,
    Ticket,
    TicketCreate,
    TicketStatus,
    TicketUpdate,
)

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


# --- board -------------------------------------------------------------------

@router.post("/{project_id}/tickets", status_code=201, tags=["board"])
def create_ticket(project_id: int, data: TicketCreate, session: Session = SessionDep) -> Ticket:
    return service.create_ticket(session, project_id, data)


@router.get("/{project_id}/tickets", tags=["board"])
def list_tickets(
    project_id: int,
    status: TicketStatus | None = None,
    assignee: str | None = None,
    session: Session = SessionDep,
) -> list[Ticket]:
    return service.list_tickets(session, project_id, status, assignee)


@router.get("/{project_id}/tickets/{number}", tags=["board"])
def get_ticket(project_id: int, number: int, session: Session = SessionDep) -> Ticket:
    return service.get_ticket(session, project_id, number)


@router.patch("/{project_id}/tickets/{number}", tags=["board"])
def update_ticket(
    project_id: int, number: int, data: TicketUpdate, session: Session = SessionDep
) -> Ticket:
    return service.update_ticket(session, project_id, number, data)


@router.post("/{project_id}/tickets/{number}/comments", status_code=201, tags=["board"])
def add_comment(
    project_id: int, number: int, data: CommentCreate, session: Session = SessionDep
) -> Comment:
    return service.add_comment(session, project_id, number, data)


@router.get("/{project_id}/tickets/{number}/comments", tags=["board"])
def list_comments(project_id: int, number: int, session: Session = SessionDep) -> list[Comment]:
    return service.list_comments(session, project_id, number)
