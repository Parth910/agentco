"""Role definitions: who each agent is and how it should work.

Prompts are short and concrete: small local models follow numbered steps and explicit
limits ("4-8 tickets", "under 400 words") much better than open-ended instructions.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session

from agentco.agents.base import Agent, EventCallback
from agentco.llm import LLMClient
from agentco.tools.base import ToolContext
from agentco.tools.toolbox import ToolBox
from agentco.tools.workspace import workspace
from agentco.workspace import service


@dataclass(frozen=True)
class Role:
    id: str
    title: str
    system_prompt: str
    max_steps: int = 20
    # Verifies the work in the workspace; returns what is missing, or None when complete.
    check_done: Callable[[ToolContext], str | None] | None = None


MIN_TICKETS = 4


def pm_check_done(ctx: ToolContext) -> str | None:
    missing = []
    if "prd" not in {d.slug for d in service.list_docs(ctx.session, ctx.project_id)}:
        missing.append('write the PRD with docs_write (slug "prd")')
    tickets = len(service.list_tickets(ctx.session, ctx.project_id))
    if tickets < MIN_TICKETS:
        missing.append(
            f"there are only {tickets} tickets; create at least {MIN_TICKETS - tickets} more "
            f"small tickets with board_create_ticket (4-8 in total)"
        )
    kickoff = service.list_messages(ctx.session, ctx.project_id, channel="general")
    if not any(m.author == ctx.actor for m in kickoff):
        missing.append('post the kickoff in channel "general" mentioning @engineer_1 and @qa')
    return "; ".join(missing) + ". Then reply with your summary." if missing else None


PM = Role(
    id="pm",
    title="Product Manager",
    max_steps=20,
    system_prompt="""\
You are the Product Manager (pm) of a small AI product team.
Teammates: engineer_1 (builds the product) and qa (tests it).
You act only by calling tools. Do one step at a time.

When the CEO gives you a product idea:
1. Write the PRD with docs_write, slug "prd", title "PRD: <product name>". Markdown sections:
   Problem, Target users, Goals, MVP features (3-5 bullets), Out of scope, Success metrics.
   Keep it under 400 words. The MVP must be small enough for one engineer to build in a few days.
2. Create 4-8 engineering tickets with board_create_ticket, one call per ticket.
   Each ticket is about half a day of work, has a specific title, a description that ends
   with "Done when: ...", priority 1-3 (1 = build first), and assignee "engineer_1".
3. Post a short kickoff message in channel "general" that summarizes the plan and
   mentions @engineer_1 and @qa.
4. Finally, reply with a 2-3 sentence summary and do not call any more tools.
""",
    check_done=pm_check_done,
)


def task_for_idea(idea: str) -> str:
    return f"New product idea from the CEO:\n\n{idea}\n\nPlan it."


def make_agent(
    role: Role,
    session: Session,
    project_id: int,
    llm: LLMClient,
    on_event: EventCallback | None = None,
) -> Agent:
    ctx = ToolContext(session, project_id, role.id)
    return Agent(
        role.id,
        role.system_prompt,
        llm,
        ToolBox.for_role(workspace, ctx),
        max_steps=role.max_steps,
        on_event=on_event,
        check_done=(lambda: role.check_done(ctx)) if role.check_done else None,
    )
