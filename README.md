# AgentCo

**Spin up a team of AI agents that works like a small product company — fully local, no API keys.**

Describe a product idea, pick a team (researcher, product manager, program manager,
engineers, QA, …), and watch them research, write a PRD, plan tickets, write code and
test it — all through an internal workspace (task board, docs, chat, git repo) that
runs on your own machine. Every step is observable.

> **Status: early development (M4).** This README describes the target experience.
> Today: `make setup` prepares your machine, the [workspace API](#workspace-api) (board,
> docs, chat, events) is live at http://localhost:8000/docs, and `make tools-demo` shows
> your local model using [agent tools](#agent-tools) as different roles. Full agents
> arrive in M5. See the [Roadmap](#roadmap).

This is a learning project for core agentic AI concepts: agent loops, tool calling,
multi-agent coordination, role permissions, shared state, human-in-the-loop and
observability.

---

## How it works

```
 You (CEO / stakeholder)
   │  "Launch: social feed app for college students"
   ▼
┌────────────────────────── Control Plane ──────────────────────────┐
│  Team Launcher  ← team.yaml (roles, models, prompts, permissions)  │
│  Runtime Config API (add/remove agent, change prompt, pause, …)    │
└──────────────────────────────┬────────────────────────────────────┘
                               ▼
┌──────────────────────────── Agent Team ───────────────────────────┐
│  Researcher → Product Manager → Program Manager → Engineers → QA  │
└──────────────────────────────┬────────────────────────────────────┘
                               ▼  agents act only through tools
┌──────────────────── Internal Workspace ("the box") ───────────────┐
│  📋 Task Board   📄 Docs   💬 Chat   🗂 Git repo   🧪 Code sandbox  │
└──────────────────────────────┬────────────────────────────────────┘
                               ▼
          Event log + traces → Observability dashboard
```

- **Agents** each have a role, a goal, a model and a set of allowed tools.
- **The workspace** is the only way agents act or talk to each other, so everything
  they do is visible and traceable.
- **The control plane** lets you configure the team at launch and change it at any time.

---

## Quick start

### Prerequisites

| Need | Why |
|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Runs the workspace, agents, dashboard and tracing |
| [Ollama](https://ollama.com) | Runs the LLM locally |
| 16 GB+ RAM recommended | 8 GB works, but slower and with a weaker model |
| ~10 GB free disk | Model + containers |
| `make` | Preinstalled on macOS/Linux (on macOS it comes with Xcode Command Line Tools) |

No API keys, accounts or internet needed after setup.

### 1. Clone and set up

```bash
git clone https://github.com/Parth910/agentco.git
cd agentco
make setup
```

`make setup` checks Docker and Ollama, picks a model for your RAM, pulls it, and starts
all services. Use `make setup MODEL=<name>` to choose a model yourself, or `YES=1` to
skip prompts:

```
✔ Docker running
✔ Ollama running
✔ Detected 18 GB RAM → recommended model: qwen3:8b
✔ Model ready
✔ Starting services (workspace, agents, dashboard, langfuse)...

🚀 AgentCo is ready → http://localhost:3000
```

| RAM | Recommended model |
|---|---|
| 8 GB | `qwen3:4b` (demo only) |
| 16–24 GB | `qwen3:8b` |
| 32 GB+ | `qwen3:14b` or larger |

> On macOS, Ollama runs natively (not in Docker) so it can use the Apple GPU.

### 2. Launch a product

Open the dashboard and click **Launch a new product**:

1. **Describe the product** — e.g. *"A simple social feed for college students: post text, like posts, see a feed."*
2. **Pick a team template**
   - `Lean Startup` — PM, 1 Engineer, QA *(default, best for local models)*
   - `Full Team` — Researcher, PM, Program Manager, 2 Engineers, QA
   - `Custom`
3. **Adjust the team** — add/remove roles, number of engineers, goals, prompts, model per role
4. **Set limits** — max runtime, max steps, which checkpoints need your approval
5. **🚀 Launch**

Or from the CLI:

```bash
./agentco launch --config teams/lean-startup.yaml --idea "Social feed app..."
```

### 3. Watch the team work

| Panel | Shows |
|---|---|
| **Team** | Each agent's status: 🧠 thinking · 🔧 using a tool · 💤 idle · ⏸ waiting for you |
| **Board** | Tickets moving through To Do → In Progress → Review → Done |
| **Chat** | Agents talking in `#general`, `#eng`, @mentioning each other |
| **Docs** | Research report, PRD, tech design as they are written |
| **Repo** | Commits and PRs from engineers |
| **Timeline** | Every event in order, with replay |
| **Traces** | Each LLM call — prompt, response, tokens, latency (Langfuse) |

```
10:02  researcher   posted "Competitor analysis" in Docs
10:09  pm           created PRD v1 → ⏸ waiting for your approval
10:11  YOU          approved PRD (comment: "skip DMs for v1")
10:12  pm           created 6 tickets on the Board
10:13  engineer_1   picked TICKET-1 "Create posts table + API"
10:25  engineer_1   opened PR #1 → assigned to qa
10:31  qa           ran tests: 2 failing → moved TICKET-1 back to In Progress
```

### 4. Interact at any time

- **Chat as the CEO** — post in `#general` (e.g. *"Pivot: make it video-first"*)
- **Approve / reject** at checkpoints, with comments
- **Edit the team live** — add an engineer, change a prompt, switch a role's model
- **Edit work directly** — create or reassign tickets, edit the PRD
- **Pause / resume / stop** the whole company or a single agent

### 5. Get the output

```
projects/social-feed-2026-10-15/
├── docs/        # research.md, prd.md, tech-design.md
├── repo/        # the code the engineers wrote (a git repo)
├── board.json   # all tickets and their history
├── chat.log     # full team conversation
└── report.md    # summary: what was built, tokens, time, open issues
```

### Everyday commands

```bash
make help                # list all commands
make start               # start services
make stop                # stop services
make restart             # restart services
make status              # what's running, is the LLM reachable
make logs                # follow logs
make llm-test            # check the LLM works (chat + structured JSON)
make tools-demo          # watch the LLM use workspace tools as different roles
make test                # run unit tests (in Docker)
```

Commands that take arguments use the `./agentco` CLI directly (`make` targets wrap it):

```bash
./agentco launch --idea "..."   # launch a team
./agentco projects              # list past runs
./agentco resume <name>         # continue a project
./agentco reset                 # wipe all data (asks first)
```

### Using a cloud model instead (optional)

Any OpenAI-compatible endpoint works. Edit `.env`:

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=<model-name>
```

Models can also be set per role, e.g. a local model for most roles and a stronger one for the PM.

---

## Workspace API

The workspace is where agents (and you) work. Everything is grouped by **project**;
data is stored in SQLite at `data/agentco.db` and survives restarts.
Interactive docs: **http://localhost:8000/docs**

| Area | Endpoints |
|---|---|
| Projects | `POST /projects` · `GET /projects` · `GET /projects/{id}` |
| Board | `POST/GET /projects/{id}/tickets` (filter `?status=` `?assignee=`) · `GET/PATCH …/tickets/{n}` · `POST/GET …/tickets/{n}/comments` |
| Docs | `PUT /projects/{id}/docs/{slug}` (create or new version) · `GET …/docs` · `GET …/docs/{slug}` · `GET …/docs/{slug}/versions[/{v}]` |
| Chat | `POST/GET /projects/{id}/channels/{channel}/messages` · `GET …/channels` · `GET /projects/{id}/messages?mention=qa` (a role's inbox) |
| Events | `GET /projects/{id}/events` (filter `?actor=` `?type=`, poll with `?after_id=`): the team timeline |

```bash
# create a project, a ticket, and move it
curl -X POST localhost:8000/projects -H 'content-type: application/json' \
  -d '{"name": "Social feed", "idea": "Feed for college students"}'
curl -X POST localhost:8000/projects/1/tickets -H 'content-type: application/json' \
  -d '{"title": "Create posts API", "assignee": "engineer_1", "priority": 1}'
curl -X PATCH localhost:8000/projects/1/tickets/1 -H 'content-type: application/json' \
  -d '{"status": "in_progress"}'

# post in chat; @mentions are detected automatically
curl -X POST localhost:8000/projects/1/channels/eng/messages -H 'content-type: application/json' \
  -d '{"author": "engineer_1", "body": "Started ticket 1, @qa review soon"}'
```

Ticket statuses: `todo → in_progress → review → done`. Priority: 1 (highest) to 3.
Send an `X-Actor: <role>` header with `PATCH` to record who made the change (default `ceo`).

---

## Agent tools

Agents act on the workspace only through **tools**: Python functions whose docstring and
Pydantic argument model become the JSON schema the LLM sees.

| Area | Tools |
|---|---|
| Board | `board_list_tickets` · `board_get_ticket` · `board_create_ticket` · `board_update_ticket` · `board_comment` |
| Docs | `docs_list` · `docs_read` · `docs_write` |
| Chat | `chat_post` · `chat_read` · `chat_inbox` (messages that @mention you) |

**Permissions.** Each role gets tool patterns (wildcards allowed). An agent only *sees*
its allowed tools; calling another returns "permission denied".

| Role | Tools |
|---|---|
| `pm` | `board_*`, `docs_*`, `chat_*` |
| `program_manager` | `board_*`, read docs, `chat_*` |
| `researcher` | read board, `docs_*`, `chat_*` |
| `engineer_N`, `qa` | read/update/comment tickets, read docs, `chat_*` (can't create tickets or write docs) |

**Built for small models:**
- Tools act as the calling role: an agent can't post or comment as someone else.
- Small mistakes are accepted: `"#eng"` → `eng`, `"Tech Design"` → `tech-design`, assignee `"me"`.
- Errors explain the fix: `Doc 'roadmap' not found. Available docs: prd, research`.
- Bad calls never crash an agent; they come back as an error it can react to.

**Everything is logged.** Each workspace change (`ticket_created`, `doc_written`, …) and
each tool call (`tool_called` with args, result, duration — including denied and failed
calls) is an event in `GET /projects/{id}/events`.

```
$ make tools-demo
[pm] Create a priority 1 ticket assigned to engineer_1 to build the API for creating posts.
  🔧 board_create_ticket({"priority":1,"assignee":"engineer_1","title":"Build the API for creating posts"…)
  ✔ {"number": 1, "title": "Build the API for creating posts", "status": "todo", …}
[engineer_1] Write the PRD document for the product.
  💬 I cannot write the PRD document for you. …
[pm] Read the PRD document.
  🔧 docs_read({"slug":"prd"})
  ✘ Doc 'prd' not found. Available docs: none, no documents exist yet
```

---

## Design notes for local models

Small local models are much weaker than frontier APIs, so the system is built around that:

- **Thinking off by default** — reasoning models like qwen3 "think" before answering
  (a one-line reply took 75 s). `LLM_REASONING_EFFORT=none` makes simple calls ~100x faster.
- **One agent at a time** — one model in memory, agents take turns.
- **Structured outputs** — every action is JSON validated against a Pydantic schema;
  on a bad reply the validation error is sent back and the model retries.
- **Small tasks** — the Program Manager breaks work into small tickets.
- **Short context** — agents read only what they need (their ticket, the relevant doc).
- **Hard limits** — max steps, max runtime, so agents can't loop forever.

---

## Project structure

```
agentco/
├── src/agentco/        # Python package
│   ├── llm/            # OpenAI-compatible LLM client
│   ├── workspace/      # Board, docs, chat: models, service (logic), api (HTTP)
│   ├── tools/          # Tool framework, workspace tools, role permissions
│   ├── agents/         # Agent loop and roles
│   ├── orchestrator/   # Team workflow (LangGraph)
│   ├── control/        # Runtime control API
│   └── observability/  # Tracing (event log lives in workspace/)
├── dashboard/          # Web UI
├── teams/              # Team templates (YAML)
├── projects/           # Run output (git-ignored)
├── tests/
└── docs/
```

---

## Roadmap

| # | Milestone | Outcome | Status |
|---|---|---|---|
| M0 | Foundation | Repo, README, structure | ✅ |
| M1 | Setup & infra | `make setup` gets a machine ready | ✅ |
| M2 | LLM client | Talks to Ollama or any OpenAI-compatible API | ✅ |
| M3 | Workspace | Board, docs, chat APIs — **v0.1.0** | ✅ |
| M4 | Tools & permissions | Agents can use workspace tools, scoped by role | ✅ |
| M5 | First agent (PM) | Idea → PRD + tickets — **v0.2.0** | ⬜ |
| M6 | Team workflow | PM → Engineer → QA end to end — **v0.3.0** | ⬜ |
| M7 | Observability | Langfuse traces, run reports | ⬜ |
| M8 | Dashboard | Watch the team live — **v0.4.0** | ⬜ |
| M9 | Config & control | Team YAML, live edits, approvals | ⬜ |
| M10 | Polish | Export, resume, docs — **v1.0.0** | ⬜ |
| Later | CI | GitHub Actions runs `make test` on every PR | ⬜ |

## Contributing

Commits follow [Conventional Commits](https://www.conventionalcommits.org)
(`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`). Each milestone is developed
on its own branch (e.g. `m1-setup`) and merged via pull request.

## License

[MIT](LICENSE)
