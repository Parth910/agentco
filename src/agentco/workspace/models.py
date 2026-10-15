"""Workspace tables and the request schemas used to create or change them."""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- projects ----------------------------------------------------------------

class ProjectCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    idea: str = ""


class Project(ProjectCreate, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow)


# --- board -------------------------------------------------------------------

class TicketStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    review = "review"
    done = "done"


class TicketCreate(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    priority: int = Field(default=2, ge=1, le=3)  # 1 = highest
    assignee: str | None = None  # a role id, e.g. "engineer_1"
    created_by: str = "ceo"


class TicketUpdate(SQLModel):
    """Only the fields that are sent get changed (send assignee: null to unassign)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=3)
    assignee: str | None = None
    status: TicketStatus | None = None


class Ticket(TicketCreate, table=True):
    __table_args__ = (UniqueConstraint("project_id", "number"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    number: int  # per project: 1, 2, 3, ...
    status: TicketStatus = TicketStatus.todo
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CommentCreate(SQLModel):
    author: str = Field(min_length=1)
    body: str = Field(min_length=1)


class Comment(CommentCreate, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)


# --- docs --------------------------------------------------------------------

class DocWrite(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = ""
    author: str = Field(min_length=1)


class Doc(DocWrite, table=True):
    __table_args__ = (UniqueConstraint("project_id", "slug"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    slug: str  # e.g. "prd", "research", "tech-design"
    version: int = 1
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DocVersion(DocWrite, table=True):
    """A snapshot of a doc each time it changes."""

    id: int | None = Field(default=None, primary_key=True)
    doc_id: int = Field(foreign_key="doc.id", index=True)
    version: int
    created_at: datetime = Field(default_factory=utcnow)


# --- chat --------------------------------------------------------------------

class MessageCreate(SQLModel):
    author: str = Field(min_length=1)
    body: str = Field(min_length=1)


class Message(MessageCreate, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    channel: str = Field(index=True)  # e.g. "general", "eng"
    mentions: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
