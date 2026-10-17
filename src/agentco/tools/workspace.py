"""Workspace tools: what agents can do on the board, in docs and in chat.

Design rules (learned from testing with small local models):
- Tools act as ctx.actor: an agent cannot post or comment as someone else.
- Return compact data so the model's context stays short.
- Accept small mistakes ("#eng" -> "eng", assignee "me").
- Errors say how to fix the call (e.g. list the docs that do exist).
"""

from pydantic import BaseModel, Field

from agentco.tools.base import Registry, ToolContext, ToolError
from agentco.workspace import service
from agentco.workspace.models import (
    CommentCreate,
    DocWrite,
    MessageCreate,
    Ticket,
    TicketCreate,
    TicketStatus,
    TicketUpdate,
)
from agentco.workspace.service import NotFoundError

workspace = Registry()


# --- helpers -----------------------------------------------------------------

def _ticket_summary(t: Ticket) -> dict:
    return {
        "number": t.number,
        "title": t.title,
        "status": t.status.value,
        "assignee": t.assignee,
        "priority": t.priority,
    }


def _resolve_role(ctx: ToolContext, role: str | None) -> str | None:
    return ctx.actor if role == "me" else role


def _channel(name: str) -> str:
    return name.strip().lstrip("#").lower()


def _slug(name: str) -> str:
    return "-".join(name.strip().lower().split())


def _get_ticket(ctx: ToolContext, number: int) -> Ticket:
    try:
        return service.get_ticket(ctx.session, ctx.project_id, number)
    except NotFoundError:
        numbers = [t.number for t in service.list_tickets(ctx.session, ctx.project_id)]
        existing = ", ".join(map(str, numbers)) or "none yet"
        raise ToolError(f"Ticket {number} not found. Existing tickets: {existing}") from None


# --- board -------------------------------------------------------------------

class ListTicketsArgs(BaseModel):
    status: TicketStatus | None = Field(default=None, description="Only tickets with this status")
    assignee: str | None = Field(
        default=None, description='Only tickets assigned to this role, e.g. "engineer_1", or "me"'
    )


@workspace.tool
def board_list_tickets(ctx: ToolContext, args: ListTicketsArgs) -> list[dict]:
    """List tickets on the task board, optionally filtered by status or assignee."""
    tickets = service.list_tickets(
        ctx.session, ctx.project_id, args.status, _resolve_role(ctx, args.assignee)
    )
    return [_ticket_summary(t) for t in tickets]


class TicketNumberArgs(BaseModel):
    number: int = Field(description="Ticket number, e.g. 3")


@workspace.tool
def board_get_ticket(ctx: ToolContext, args: TicketNumberArgs) -> dict:
    """Get one ticket with its full description and comments."""
    ticket = _get_ticket(ctx, args.number)
    comments = service.list_comments(ctx.session, ctx.project_id, args.number)
    return {
        **_ticket_summary(ticket),
        "description": ticket.description,
        "created_by": ticket.created_by,
        "comments": [{"author": c.author, "body": c.body} for c in comments],
    }


class CreateTicketArgs(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="Short, specific task title")
    description: str = Field(default="", description="What to do and how to know it is done")
    priority: int = Field(default=2, ge=1, le=3, description="1 = highest, 3 = lowest")
    assignee: str | None = Field(default=None, description='Role to assign, e.g. "engineer_1"')


@workspace.tool
def board_create_ticket(ctx: ToolContext, args: CreateTicketArgs) -> dict:
    """Create a ticket on the task board. It starts in status "todo"."""
    data = TicketCreate(**args.model_dump(), created_by=ctx.actor)
    data.assignee = _resolve_role(ctx, data.assignee)
    return _ticket_summary(service.create_ticket(ctx.session, ctx.project_id, data))


class UpdateTicketArgs(BaseModel):
    number: int = Field(description="Ticket number")
    status: TicketStatus | None = Field(default=None, description="New status")
    assignee: str | None = Field(default=None, description='New assignee role, or "me"')
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=3)


@workspace.tool
def board_update_ticket(ctx: ToolContext, args: UpdateTicketArgs) -> dict:
    """Change a ticket: move its status (todo, in_progress, review, done), reassign it,
    or edit its title, description or priority. Only the fields you give are changed."""
    changes = args.model_dump(exclude={"number"}, exclude_none=True)
    if not changes:
        raise ToolError("Nothing to update: give at least one of status, assignee, title, description, priority")
    if "assignee" in changes:
        changes["assignee"] = _resolve_role(ctx, changes["assignee"])
    _get_ticket(ctx, args.number)
    ticket = service.update_ticket(
        ctx.session, ctx.project_id, args.number, TicketUpdate(**changes), actor=ctx.actor
    )
    return _ticket_summary(ticket)


class CommentArgs(BaseModel):
    number: int = Field(description="Ticket number")
    body: str = Field(min_length=1, description="The comment")


@workspace.tool
def board_comment(ctx: ToolContext, args: CommentArgs) -> dict:
    """Add a comment to a ticket (progress notes, review feedback, questions)."""
    _get_ticket(ctx, args.number)
    service.add_comment(
        ctx.session, ctx.project_id, args.number, CommentCreate(author=ctx.actor, body=args.body)
    )
    return {"number": args.number, "commented": True}


# --- docs --------------------------------------------------------------------

class NoArgs(BaseModel):
    pass


@workspace.tool
def docs_list(ctx: ToolContext, args: NoArgs) -> list[dict]:
    """List the project's documents (slug, title, version, last author)."""
    return [
        {"slug": d.slug, "title": d.title, "version": d.version, "author": d.author}
        for d in service.list_docs(ctx.session, ctx.project_id)
    ]


class DocSlugArgs(BaseModel):
    slug: str = Field(description='Document id, e.g. "prd", "research", "tech-design"')


@workspace.tool
def docs_read(ctx: ToolContext, args: DocSlugArgs) -> dict:
    """Read a document's full content."""
    slug = _slug(args.slug)
    try:
        doc = service.get_doc(ctx.session, ctx.project_id, slug)
    except NotFoundError:
        slugs = [d.slug for d in service.list_docs(ctx.session, ctx.project_id)]
        available = ", ".join(slugs) if slugs else "none, no documents exist yet"
        raise ToolError(f"Doc '{slug}' not found. Available docs: {available}") from None
    return {"slug": doc.slug, "title": doc.title, "version": doc.version, "content": doc.content}


class DocWriteArgs(BaseModel):
    slug: str = Field(description='Document id: lowercase words with dashes, e.g. "prd", "tech-design"')
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(description="Full document content in Markdown (replaces the old content)")


@workspace.tool
def docs_write(ctx: ToolContext, args: DocWriteArgs) -> dict:
    """Create a document, or replace its content (the old content is kept as a previous version)."""
    doc = service.write_doc(
        ctx.session,
        ctx.project_id,
        _slug(args.slug),
        DocWrite(title=args.title, content=args.content, author=ctx.actor),
    )
    return {"slug": doc.slug, "version": doc.version}


# --- chat --------------------------------------------------------------------

class ChatPostArgs(BaseModel):
    channel: str = Field(description='Channel name, e.g. "general" or "eng"')
    body: str = Field(min_length=1, description='Message text. Use @role to mention, e.g. "@qa"')


@workspace.tool
def chat_post(ctx: ToolContext, args: ChatPostArgs) -> dict:
    """Post a message in a team chat channel. Mention roles with @role to get their attention."""
    message = service.post_message(
        ctx.session, ctx.project_id, _channel(args.channel), MessageCreate(author=ctx.actor, body=args.body)
    )
    return {"id": message.id, "channel": message.channel, "mentions": message.mentions}


class ChatReadArgs(BaseModel):
    channel: str = Field(description='Channel name, e.g. "general"')
    limit: int = Field(default=20, ge=1, le=50, description="How many recent messages")


@workspace.tool
def chat_read(ctx: ToolContext, args: ChatReadArgs) -> list[dict]:
    """Read the most recent messages in a channel, oldest first."""
    messages = service.list_messages(
        ctx.session, ctx.project_id, channel=_channel(args.channel), limit=args.limit
    )
    return [{"id": m.id, "author": m.author, "body": m.body} for m in messages]


class InboxArgs(BaseModel):
    after_id: int = Field(default=0, description="Only messages newer than this message id")


@workspace.tool
def chat_inbox(ctx: ToolContext, args: InboxArgs) -> list[dict]:
    """Messages in any channel that @mention you."""
    messages = service.list_messages(
        ctx.session, ctx.project_id, mention=ctx.actor, after_id=args.after_id
    )
    return [{"id": m.id, "channel": m.channel, "author": m.author, "body": m.body} for m in messages]
