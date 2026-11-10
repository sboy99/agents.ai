# Pudding - Idea to Implementation Pipeline

## Overview

**Pudding** transforms raw product ideas into implementation-ready tickets. It's a LangGraph-powered pipeline that:

1. **Ingests** an idea from user input
2. **Researches** the market using Tavily search
3. **Clarifies** with the user via interrupt points
4. **Analyzes** for go/no-go decision with risk scoring
5. **Writes** HLD/LLD specs with Mermaid diagrams
6. **Publishes** to Notion (best-effort, fails gracefully)
7. **Generates** implementation tickets for engineering

---

## Architecture

### Module Structure

```
src/
├── puding/           # Entry point (CLI & server)
│   ├── __init__.py   # CLI entry point with streaming support
│   └── server.py     # Dev server runner (uv run dev-server)
├── graph.py          # LangGraph state machine builder
├── types.py          # Domain types: Phase, ProductState, Pydantic models
├── config.py         # Pydantic-settings configuration
├── main.py           # FastAPI application
│
├── services/         # Cross-cutting concerns
│   ├── llm.py           # LLM client factory
│   ├── prompt_builder.py # Prompt loading + caching
│   └── task_store.py    # SQLite task persistence
│
├── mcp/              # MCP (Model Context Protocol) clients
│   ├── client.py      # MCPManager: tool orchestration
│   ├── oauth.py       # OAuth client registration + PKCE
│   └── token_store.py # OAuth token persistence
│
├── nodes/            # LangGraph nodes (graph stages)
│   ├── ingest.py      # Extract and normalize idea
│   ├── research.py    # Search + dossier generation
│   ├── clarify.py     # User interrupts for questions
│   ├── analyze.py     # Risk scoring, go/no-go verdict
│   ├── write_spec.py  # HLD/LLD generation
│   ├── publish_notion.py # Best-effort Notion publish
│   └── generate_tickets.py # Ticket creation + Linear sync
│
├── api/              # FastAPI routes
│   ├── ideas.py   # GET/POST for starting ideas
│   ├── tasks.py   # CRUD for tasks
│   └── auth.py    # OAuth endpoints
│
└── config.py        # Application configuration
```

### The Pipeline Flow

```
┌─────────┐
│ IDEA    │
└──┬──────┘
   ▼
┌─────────┐    ┌─────────────────┐
│ ingest  │───▶│ research        │───▶ tavily_search
└─────────┘    └────────┬────────┘
                        ▼
                ┌───────────────┐
                │ clarify       │───▶ User interrupt point
                └──────┬────────┘   (optional)
                       ▼
                ┌───────────────┐
                │ analyze       │───▶ go/no-go decision
                └──────┬────────┘
                       ▼
                ┌───────────────┐
                │ write_spec    │───▶ HLD/LLD + diagrams
                └──────┬────────┘
                       ▼
                ┌───────────────┐
                │publish_notion │───▶ Best-effort Notion
                └──────┬────────┘   (fails gracefully)
                       ▼
                ┌───────────────┐
                │generate_tickets│──▶ SQLite + Linear
                └───────────────┘
```

---

## Key Concepts

### Phases

The `Phase` enum drives the pipeline state machine:
- `IDEA` → Initial ingestion
- `PLANNED` → Research/analysis complete, ready for next stage
- `SPEC` → Spec generated, awaiting ticket generation
- `TASKS` → Tickets generated and persisted

### ProductState

The shared state dictionary passed through the graph:
```python
class ProductState(TypedDict, total=False):
    phase: Phase
    idea: str
    research: dict           # ResearchDossier as dict
    answers: dict[str, str]  # User clarifications
    pending_questions: list  # Questions awaiting user input
    scorecard: dict          # Scorecard with verdict
    docs: dict               # Docs with HLD/LLD
    notion_parent_id: str | None
    tickets: list[dict]      # Generated tickets
```

### Seams and Adapters

The codebase places seams at key integration points:

**External integrations** (MCP adapters):
- Tavily search → `tavily_search` tool
- Notion pages → `notion_pages_create` tool  
- Linear issues → `issueCreate` tool

**Persistence adapters**:
- `TaskStore` → SQLite task database
- `TokenStore` → SQLite OAuth tokens
- `AsyncSqliteSaver` → LangGraph checkpoint state

---

## Configuration

Required environment variables (`.env`):
```
LLM_API_KEY=<your-openai-key>
LLM_MODEL=gpt-4.1-mini
LLM_BASE_URL=https://api.openai.com/v1
OAUTH_REDIRECT_URI=http://localhost:8000/callback
```

Optional:
```
TAVILY_API_KEY=<your-key>
NOTION_PARENT_DB_ID=<database-id>
```

Database location: `.puding/db/` (auto-created)

---

## Prompts

The pipeline uses prompt templates for LLM instructions:

| Prompt | Stage | Purpose |
|--------|-------|---------|
| `research.md` | Research | Generate market dossier from search results |
| `analyze.md` | Analysis | Go/no-go scorecard with risk matrix |
| `task_brief.md` | Ticket | Individual task brief for engineers |
| `spec.md` | Spec | HLD/LLD generation |
| `prd.md` | Tickets | Convert spec into ordered tickets |
| `task_brief.md` | Tasks | Render task as Claude prompt |

---

## Testing

Run tests with:
```bash
uv run pytest tests/ -v
```

Current test setup:
- `tests/__init__.py` - Test package marker
- Uses pytest with no additional test dependencies

---

## Development

### CLI Usage

```bash
# Run the pipeline
uv run puding

# With verbose logging
uv run puding -v

# Development server
uv run dev-server  # Requires uv sync --extra dev
```

### API Usage

```bash
# Start an idea
curl -X POST /ideas -d '{"idea": "Build a todo app"}'

# List tasks
curl GET /tasks?thread_id=<thread_id>

# Get current task
curl GET /tasks/current?thread_id=<thread_id>

# Move task status
curl -X POST /tasks/TASK-001/move -d '{"status": "in_progress"}'
```

### Hot Reload

The `dev-server` command enables auto-reload:
```bash
uv run dev-server
# Navigate to http://127.0.0.1:8000/docs
```

---

## Integration Points

### MCP Servers

The pipeline integrates with external services via MCP:

1. **Tavily Search** - Research phase uses `tavily_search` tool
2. **Notion** - Spec phase publishes via `notion_pages_create` tool
3. **Linear** - Ticket phase creates issues via `issueCreate` tool

If MCP servers are unavailable, the pipeline continues with local persistence.

### OAuth Flow

For Notion and Linear, users must complete OAuth:
1. Visit `/auth/{server}/login` to register
2. Complete authorization with the service
3. Tokens are stored in the SQLite token database

---

## Domain Glossary

- **Idea** - Raw product concept from user input
- **Research** - Market analysis from search results
- **Dossier** - Structured research output (summary, competitors, risks, etc.)
- **Clarification** - User answers to open questions
- **Scorecard** - Go/no-go decision with risk matrix
- **Spec** - High-level and low-level design documents
- **Ticket** - Implementation task for an engineer
- **Thread** - Conversation context identified by `thread_id`

---

## Common Patterns

### Fail-Soft Pattern

External integrations use best-effort with graceful degradation:
```python
try:
    tool = await mcp.get_tool("notion_pages_create")
except RuntimeError:
    # Log locally, continue pipeline
    logger.warning("Notion MCP unavailable")
```

### State Graph Pattern

Each node receives `ProductState` and returns partial updates:
```python
async def research(state: ProductState) -> ProductState:
    # Returns only what changed
    return {"research": dossier, "phase": Phase.PLANNED}
```

### LLM Structured Output

All LLM calls use Pydantic models for type safety:
```python
llm = get_llm()
result = await llm.with_structured_output(ResearchDossier).ainvoke([...])
```

---

## Reference

- [TASKS.md](TASKS.md) - Detailed implementation roadmap
- [prompts/](prompts/) - LLM prompt templates
- [.env.example](.env) - Environment configuration template