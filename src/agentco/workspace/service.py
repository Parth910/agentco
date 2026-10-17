"""Workspace logic. Used by the HTTP API and (from M4) directly by agent tools."""

import re

from sqlmodel import Session, func, select

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
    utcnow,
)


class NotFoundError(Exception):
    pass


class InvalidError(Exception):
    """The request is well-formed but not allowed (e.g. a bad doc slug)."""


SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
# "@pm" counts only at a word start, so emails like "a@b.com" are not mentions.
MENTION_PATTERN = re.compile(r"(?<![\w@])@([a-z0-9_]+)")


# --- events ------------------------------------------------------------------

def log_event(session: Session, project_id: int, actor: str, type: str, **data) -> Event:
    """Add an event to the session; it is saved with the caller's next commit."""
    event = Event(project_id=project_id, actor=actor, type=type, data=data)
    session.add(event)
    return event


def list_events(
    session: Session,
    project_id: int,
    actor: str | None = None,
    type: str | None = None,
    after_id: int = 0,
    limit: int = 100,
) -> list[Event]:
    """Events oldest-first. With after_id: only newer ones. Without: the latest `limit`."""
    get_project(session, project_id)
    query = select(Event).where(Event.project_id == project_id, Event.id > after_id)
    if actor:
        query = query.where(Event.actor == actor)
    if type:
        query = query.where(Event.type == type)
    events = list(session.exec(query.order_by(Event.id)))
    return events[:limit] if after_id else events[-limit:]


# --- projects ----------------------------------------------------------------

def create_project(session: Session, data: ProjectCreate) -> Project:
    project = Project.model_validate(data)
    session.add(project)
    session.flush()
    log_event(session, project.id, "ceo", "project_created", name=project.name)
    session.commit()
    session.refresh(project)
    return project


def list_projects(session: Session) -> list[Project]:
    return list(session.exec(select(Project).order_by(Project.id.desc())))


def get_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if not project:
        raise NotFoundError(f"Project {project_id} not found")
    return project


# --- board -------------------------------------------------------------------

def create_ticket(session: Session, project_id: int, data: TicketCreate) -> Ticket:
    get_project(session, project_id)
    last = session.exec(
        select(func.max(Ticket.number)).where(Ticket.project_id == project_id)
    ).one()
    ticket = Ticket.model_validate(data, update={"project_id": project_id, "number": (last or 0) + 1})
    session.add(ticket)
    log_event(
        session, project_id, data.created_by, "ticket_created",
        number=ticket.number, title=ticket.title, assignee=ticket.assignee,
    )
    session.commit()
    session.refresh(ticket)
    return ticket


def list_tickets(
    session: Session,
    project_id: int,
    status: TicketStatus | None = None,
    assignee: str | None = None,
) -> list[Ticket]:
    get_project(session, project_id)
    query = select(Ticket).where(Ticket.project_id == project_id)
    if status:
        query = query.where(Ticket.status == status)
    if assignee:
        query = query.where(Ticket.assignee == assignee)
    return list(session.exec(query.order_by(Ticket.number)))


def get_ticket(session: Session, project_id: int, number: int) -> Ticket:
    ticket = session.exec(
        select(Ticket).where(Ticket.project_id == project_id, Ticket.number == number)
    ).first()
    if not ticket:
        raise NotFoundError(f"Ticket {number} not found in project {project_id}")
    return ticket


def update_ticket(
    session: Session, project_id: int, number: int, data: TicketUpdate, actor: str = "ceo"
) -> Ticket:
    ticket = get_ticket(session, project_id, number)
    changes = data.model_dump(mode="json", exclude_unset=True)
    # Only assignee may be cleared with null; ignore null for required fields.
    changes = {k: v for k, v in changes.items() if v is not None or k == "assignee"}
    if changes:
        ticket.sqlmodel_update(changes)
        ticket.updated_at = utcnow()
        session.add(ticket)
        log_event(session, project_id, actor, "ticket_updated", number=number, changes=changes)
        session.commit()
        session.refresh(ticket)
    return ticket


def add_comment(session: Session, project_id: int, number: int, data: CommentCreate) -> Comment:
    ticket = get_ticket(session, project_id, number)
    comment = Comment.model_validate(data, update={"ticket_id": ticket.id})
    session.add(comment)
    log_event(session, project_id, data.author, "comment_added", number=number)
    session.commit()
    session.refresh(comment)
    return comment


def list_comments(session: Session, project_id: int, number: int) -> list[Comment]:
    ticket = get_ticket(session, project_id, number)
    return list(session.exec(select(Comment).where(Comment.ticket_id == ticket.id).order_by(Comment.id)))


# --- docs --------------------------------------------------------------------

def write_doc(session: Session, project_id: int, slug: str, data: DocWrite) -> Doc:
    """Create the doc, or update it as a new version. Unchanged writes add no version."""
    if not SLUG_PATTERN.match(slug):
        raise InvalidError(f"Invalid doc slug '{slug}': use lowercase letters, digits and dashes")
    get_project(session, project_id)

    doc = session.exec(select(Doc).where(Doc.project_id == project_id, Doc.slug == slug)).first()
    if doc is None:
        doc = Doc.model_validate(data, update={"project_id": project_id, "slug": slug})
    elif (doc.title, doc.content) == (data.title, data.content):
        return doc
    else:
        doc.sqlmodel_update(data.model_dump())
        doc.version += 1
        doc.updated_at = utcnow()

    session.add(doc)
    session.flush()  # assigns doc.id for a new doc
    session.add(DocVersion.model_validate(data, update={"doc_id": doc.id, "version": doc.version}))
    log_event(session, project_id, data.author, "doc_written", slug=slug, version=doc.version)
    session.commit()
    session.refresh(doc)
    return doc


def list_docs(session: Session, project_id: int) -> list[Doc]:
    get_project(session, project_id)
    return list(session.exec(select(Doc).where(Doc.project_id == project_id).order_by(Doc.slug)))


def get_doc(session: Session, project_id: int, slug: str) -> Doc:
    doc = session.exec(select(Doc).where(Doc.project_id == project_id, Doc.slug == slug)).first()
    if not doc:
        raise NotFoundError(f"Doc '{slug}' not found in project {project_id}")
    return doc


def list_doc_versions(session: Session, project_id: int, slug: str) -> list[DocVersion]:
    doc = get_doc(session, project_id, slug)
    return list(
        session.exec(select(DocVersion).where(DocVersion.doc_id == doc.id).order_by(DocVersion.version))
    )


def get_doc_version(session: Session, project_id: int, slug: str, version: int) -> DocVersion:
    doc = get_doc(session, project_id, slug)
    snapshot = session.exec(
        select(DocVersion).where(DocVersion.doc_id == doc.id, DocVersion.version == version)
    ).first()
    if not snapshot:
        raise NotFoundError(f"Doc '{slug}' has no version {version}")
    return snapshot


# --- chat --------------------------------------------------------------------

def parse_mentions(body: str) -> list[str]:
    """'@pm and @qa, @pm' -> ['pm', 'qa'] (order kept, no duplicates)."""
    return list(dict.fromkeys(MENTION_PATTERN.findall(body)))


def post_message(session: Session, project_id: int, channel: str, data: MessageCreate) -> Message:
    if not SLUG_PATTERN.match(channel):
        raise InvalidError(f"Invalid channel '{channel}': use lowercase letters, digits and dashes")
    get_project(session, project_id)
    message = Message.model_validate(
        data,
        update={"project_id": project_id, "channel": channel, "mentions": parse_mentions(data.body)},
    )
    session.add(message)
    session.flush()
    log_event(
        session, project_id, data.author, "message_posted",
        channel=channel, message_id=message.id, mentions=message.mentions,
    )
    session.commit()
    session.refresh(message)
    return message


def list_channels(session: Session, project_id: int) -> list[str]:
    get_project(session, project_id)
    query = select(Message.channel).where(Message.project_id == project_id).distinct()
    return sorted(session.exec(query))


def list_messages(
    session: Session,
    project_id: int,
    channel: str | None = None,
    mention: str | None = None,
    after_id: int = 0,
    limit: int = 50,
) -> list[Message]:
    """Messages oldest-first. With after_id: only newer ones (for polling).
    Without: the latest `limit` messages."""
    get_project(session, project_id)
    query = select(Message).where(Message.project_id == project_id, Message.id > after_id)
    if channel:
        query = query.where(Message.channel == channel)
    messages = list(session.exec(query.order_by(Message.id)))
    if mention:
        # Filtered in Python: simple, and fine at workspace scale.
        messages = [m for m in messages if mention in m.mentions]
    return messages[:limit] if after_id else messages[-limit:]
