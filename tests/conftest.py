import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from agentco.server import create_app
from agentco.workspace.db import init_db


@pytest.fixture
def engine():
    # One shared in-memory database per test (StaticPool keeps a single connection).
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def api(engine):
    with TestClient(create_app(engine)) as client:
        yield client


@pytest.fixture
def project(api) -> dict:
    return api.post("/projects", json={"name": "Social feed", "idea": "Feed for students"}).json()
