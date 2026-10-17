"""Launch a product: create a project and let the team work on the idea.

For now the team is the PM agent (M5): it writes the PRD, creates tickets and posts
a kickoff. Engineers and QA join in M6.

Run inside the container: ./agentco launch --idea "..."  (or make launch IDEA="...")
"""

import argparse
import json
import sys

from sqlmodel import Session

from agentco.agents.roles import PM, make_agent, task_for_idea
from agentco.llm import LLMClient
from agentco.workspace import service
from agentco.workspace.db import init_db, make_engine
from agentco.workspace.models import ProjectCreate

API = "http://localhost:8000"


def short(value, limit=90) -> str:
    text = value if isinstance(value, str) else json.dumps(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def name_from_idea(idea: str) -> str:
    words = idea.replace(":", " ").split()
    return short(" ".join(words[:6]), 60)


def show_progress(kind: str, data: dict) -> None:
    if kind == "tool":
        mark = "✔" if data["ok"] else "✘"
        print(f"  [{data['step']:>2}] 🔧 {data['name']}({short(data['arguments'], 70)})")
        print(f"       {mark} {short(data['result'])}")
    elif kind == "message":
        print(f"  [{data['step']:>2}] 💬 {short(data['text'], 200)}")
    elif kind == "nudge":
        print(f"  [{data['step']:>2}] ↩︎  Not done yet: {short(data['text'], 200)}")
    elif kind == "error":
        print(f"  [{data['step']:>2}] ✘ {data['error']}")


def print_results(session: Session, project_id: int) -> None:
    for doc in service.list_docs(session, project_id):
        words = len(doc.content.split())
        print(f"\n📄 {doc.title}  (v{doc.version}, {words} words)\n")
        print("\n".join(f"   {line}" for line in doc.content.strip().splitlines()))

    tickets = service.list_tickets(session, project_id)
    print(f"\n📋 Board: {len(tickets)} tickets")
    for t in tickets:
        print(f"   #{t.number} P{t.priority} {t.title}  → {t.assignee or 'unassigned'}")

    for m in service.list_messages(session, project_id, channel="general"):
        print(f"\n💬 #general  {m.author}: {short(m.body, 300)}")

    print("\nSee everything:")
    print(f"   PRD       {API}/projects/{project_id}/docs/prd")
    print(f"   Board     {API}/projects/{project_id}/tickets")
    print(f"   Timeline  {API}/projects/{project_id}/events")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentco launch", description=__doc__.splitlines()[0])
    parser.add_argument("--idea", required=True, help="The product idea, in a sentence or two")
    parser.add_argument("--name", help="Project name (default: from the idea)")
    args = parser.parse_args(argv)

    engine = make_engine()
    init_db(engine)
    llm = LLMClient()

    with Session(engine) as session:
        name = args.name or name_from_idea(args.idea)
        project_id = service.create_project(session, ProjectCreate(name=name, idea=args.idea)).id
        print(f'🚀 Launching "{name}"  (project {project_id})')
        print(f"   Team: {PM.title} (pm)   Model: {llm.config.model}\n")
        print(f"[pm] {short(args.idea, 150)}")

        agent = make_agent(PM, session, project_id, llm, on_event=show_progress)
        run = agent.run(task_for_idea(args.idea))

        tokens = run.prompt_tokens + run.completion_tokens
        status = "✔ PM finished" if run.stop_reason == "done" else f"✘ PM stopped ({run.stop_reason})"
        print(
            f"\n{status} in {run.duration_s:.0f}s · {run.steps} steps · "
            f"{run.tool_calls} tool calls · {run.nudges} nudges · {tokens:,} tokens"
        )
        if run.final_text:
            print(f"   {short(run.final_text, 300)}")
        print_results(session, project_id)

    return 0 if run.stop_reason == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
