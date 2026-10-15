"""SQLite database setup for the workspace."""

import os
from pathlib import Path

from sqlalchemy import Engine, event
from sqlmodel import SQLModel, create_engine

DEFAULT_DATABASE_URL = "sqlite:///data/agentco.db"


def make_engine(url: str | None = None) -> Engine:
    url = url or os.getenv("AGENTCO_DATABASE_URL") or DEFAULT_DATABASE_URL

    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread=False: FastAPI may use the connection from another thread.
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys = ON")

    return engine


def init_db(engine: Engine) -> None:
    """Create any missing tables. Models must be imported before calling this."""
    from agentco.workspace import models  # noqa: F401  (registers the tables)

    SQLModel.metadata.create_all(engine)
