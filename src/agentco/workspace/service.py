"""Workspace logic. Used by the HTTP API and (from M4) directly by agent tools."""

from sqlmodel import Session, select

from agentco.workspace.models import Project, ProjectCreate


class NotFoundError(Exception):
    pass


# --- projects ----------------------------------------------------------------

def create_project(session: Session, data: ProjectCreate) -> Project:
    project = Project.model_validate(data)
    session.add(project)
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
