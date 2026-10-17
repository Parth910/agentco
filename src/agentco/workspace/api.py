"""HTTP API for the workspace. Thin layer over service.py."""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlmodel import Session

from agentco.workspace import service
from agentco.workspace.models import (
    Comment,
    CommentCreate,
    Doc,
    DocVersion,
    DocWrite,
    Event,
    Message,
    MessageCreate,
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
    project_id: int,
    number: int,
    data: TicketUpdate,
    x_actor: str = Header(default="ceo", description="Who is making the change"),
    session: Session = SessionDep,
) -> Ticket:
    return service.update_ticket(session, project_id, number, data, actor=x_actor)


@router.post("/{project_id}/tickets/{number}/comments", status_code=201, tags=["board"])
def add_comment(
    project_id: int, number: int, data: CommentCreate, session: Session = SessionDep
) -> Comment:
    return service.add_comment(session, project_id, number, data)


@router.get("/{project_id}/tickets/{number}/comments", tags=["board"])
def list_comments(project_id: int, number: int, session: Session = SessionDep) -> list[Comment]:
    return service.list_comments(session, project_id, number)


# --- docs --------------------------------------------------------------------

@router.put("/{project_id}/docs/{slug}", tags=["docs"])
def write_doc(project_id: int, slug: str, data: DocWrite, session: Session = SessionDep) -> Doc:
    """Create or update a doc. Each change is saved as a new version."""
    return service.write_doc(session, project_id, slug, data)


@router.get("/{project_id}/docs", tags=["docs"])
def list_docs(project_id: int, session: Session = SessionDep) -> list[Doc]:
    return service.list_docs(session, project_id)


@router.get("/{project_id}/docs/{slug}", tags=["docs"])
def get_doc(project_id: int, slug: str, session: Session = SessionDep) -> Doc:
    return service.get_doc(session, project_id, slug)


@router.get("/{project_id}/docs/{slug}/versions", tags=["docs"])
def list_doc_versions(project_id: int, slug: str, session: Session = SessionDep) -> list[DocVersion]:
    return service.list_doc_versions(session, project_id, slug)


@router.get("/{project_id}/docs/{slug}/versions/{version}", tags=["docs"])
def get_doc_version(
    project_id: int, slug: str, version: int, session: Session = SessionDep
) -> DocVersion:
    return service.get_doc_version(session, project_id, slug, version)


# --- chat --------------------------------------------------------------------

@router.post("/{project_id}/channels/{channel}/messages", status_code=201, tags=["chat"])
def post_message(
    project_id: int, channel: str, data: MessageCreate, session: Session = SessionDep
) -> Message:
    """Post to a channel. @mentions in the body are detected automatically."""
    return service.post_message(session, project_id, channel, data)


@router.get("/{project_id}/channels", tags=["chat"])
def list_channels(project_id: int, session: Session = SessionDep) -> list[str]:
    return service.list_channels(session, project_id)


@router.get("/{project_id}/channels/{channel}/messages", tags=["chat"])
def list_channel_messages(
    project_id: int,
    channel: str,
    after_id: int = 0,
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = SessionDep,
) -> list[Message]:
    return service.list_messages(session, project_id, channel=channel, after_id=after_id, limit=limit)


@router.get("/{project_id}/messages", tags=["chat"])
def list_messages(
    project_id: int,
    mention: str | None = None,
    after_id: int = 0,
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = SessionDep,
) -> list[Message]:
    """Messages across all channels; use ?mention=pm for a role's inbox."""
    return service.list_messages(session, project_id, mention=mention, after_id=after_id, limit=limit)


# --- events ------------------------------------------------------------------

@router.get("/{project_id}/events", tags=["events"])
def list_events(
    project_id: int,
    actor: str | None = None,
    type: str | None = None,
    after_id: int = 0,
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = SessionDep,
) -> list[Event]:
    """The team timeline: every change, who made it, and (from agents) every tool call."""
    return service.list_events(session, project_id, actor, type, after_id, limit)
