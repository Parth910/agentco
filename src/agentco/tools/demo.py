"""Watch the real LLM use workspace tools, one small task per role.

Each task is a single LLM call: the model sees only its role's tools, picks one,
and the ToolBox runs it. (Multi-step agents that loop until done arrive in M5.)

Run inside the container with `make tools-demo`.
"""

import json
import sys
from datetime import datetime

from sqlmodel import Session

from agentco.llm import LLMClient
from agentco.tools.base import ToolContext
from agentco.tools.toolbox import ToolBox
from agentco.tools.workspace import workspace
from agentco.workspace import service
from agentco.workspace.db import init_db, make_engine
from agentco.workspace.models import ProjectCreate

TASKS = [
    ("pm", "Create a priority 1 ticket assigned to engineer_1 to build the API for creating posts."),
    ("pm", "Post in #eng asking @engineer_1 to start on ticket 1."),
    ("engineer_1", "Move ticket 1 to in progress."),
    ("engineer_1", "Write the PRD document for the product."),  # not allowed for engineers
    ("pm", "Read the PRD document."),  # does not exist yet
]

SYSTEM = (
    "You are {role}, a member of a small product team. "
    "Do the task by calling exactly one tool. If none of your tools can do it, say so briefly."
)


def short(value, limit=110) -> str:
    text = value if isinstance(value, str) else json.dumps(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main() -> int:
    engine = make_engine()
    init_db(engine)
    llm = LLMClient()

    with Session(engine) as session:
        name = f"Tools demo {datetime.now():%H:%M:%S}"
        project_id = service.create_project(session, ProjectCreate(name=name, idea="Social feed app")).id
        print(f"Project {project_id}: {name}  (model: {llm.config.model})\n")

        for role, task in TASKS:
            box = ToolBox.for_role(workspace, ToolContext(session, project_id, role))
            print(f"[{role}] {task}")
            try:
                reply = llm.chat(task, system=SYSTEM.format(role=role), tools=box.schemas())
            except Exception as exc:
                print(f"  ✘ LLM call failed: {exc}")
                return 1

            if not reply.tool_calls:
                print(f"  💬 {short(reply.text.strip())}")
            for call in reply.tool_calls:
                result = box.call(call.name, call.arguments)
                print(f"  🔧 {call.name}({short(call.arguments, 80)})")
                print(f"  {'✔' if result.ok else '✘'} {short(result.data if result.ok else result.error)}")
            print(f"  ({reply.latency_s:.1f}s)\n")

    print(f"Timeline of everything above: http://localhost:8000/projects/{project_id}/events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
