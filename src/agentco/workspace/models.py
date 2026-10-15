"""Workspace tables and the request schemas used to create or change them."""

from datetime import datetime, timezone

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
