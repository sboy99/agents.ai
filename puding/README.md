# Pudding - Idea to Implementation Pipeline

Pudding transforms raw product ideas into implementation-ready tickets. It's a LangGraph-powered pipeline that:

1. **Ingests** an idea from user input
2. **Researches** the market using Tavily search
3. **Clarifies** with the user via interrupt points
4. **Analyzes** for go/no-go decision with risk scoring
5. **Writes** HLD/LLD specs with Mermaid diagrams
6. **Publishes** to Notion (best-effort, fails gracefully)
7. **Generates** implementation tickets for engineering

---

## Architecture

### Graph Structure

The pipeline is implemented as a **LangGraph state machine** that orchestrates the flow between phases. The graph is defined in `src/graph.py` and compiled with an async SQLite checkpointer for durable state persistence.

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

### Phase Enum

The `Phase` enum in `src/types.py` drives the pipeline state machine:

- `IDEA` → Initial ingestion
- `PLANNED` → Research/analysis complete, ready for next stage
- `SPEC` → Spec generated, awaiting ticket generation
- `TASKS` → Tickets generated and persisted

### ProductState

The shared state dictionary passed through the graph, defined in `src/types.py`:

```python
class ProductState(TypedDict, total=False):
    phase: Phase                           # Current pipeline phase
    idea: str                                # Raw product concept
    research: dict                           # ResearchDossier as dict
    answers: dict[str, str]                  # User clarifications
    pending_questions: list                    # Questions awaiting user input
    scorecard: dict                          # Scorecard with verdict
    docs: dict                                 # Docs with HLD/LLD
    notion_parent_id: str | None               # Notion page parent ID
    tickets: list[dict]                        # Generated tickets
```

---

## Component Deep Dive

### Entry Points

#### CLI (`src/puding/cli.py`)
The command-line interface provides an interactive experience for running the pipeline:
- Accepts user input via stdin
- Calls `build_graph()` from `src/graph.py`
- Handles clarification interrupts via `pending_questions()` helper
- Displays final phase, verdict, and ticket count

#### FastAPI Server (`src/api/`)
REST API for programmatic access:
- `src/api/__init__.py` - App factory with lifespan management
- `src/api/ideas.py` - POST `/ideas` to start a new pipeline run
- `src/api/tasks.py` - CRUD operations for tickets with SSE streaming
- `src/api/auth.py` - OAuth endpoints for Notion/Linear

### LangGraph Nodes (`src/nodes/`)

Each node is a pure async function that receives `ProductState` and returns a partial update.

#### 1. `ingest.py` - Idea Ingestion
**Purpose**: Extract and normalize the incoming idea text.

**How it works**:
- Receives raw idea string from user input
- Strips whitespace and normalizes formatting
- Transitions state to `Phase.IDEA`
- No external calls - purely local processing

```python
def ingest(state: ProductState) -> ProductState:
    idea = state.get("idea", "").strip()
    return {"phase": Phase.IDEA, "idea": idea}
```

#### 2. `research.py` - Market Research
**Purpose**: Generate a market dossier from search results.

**How it works**:
- Builds 4 search queries based on the idea:
  - `{idea} market competitors`
  - `{idea} existing products alternatives`
  - `{idea} risks challenges regulation`
  - `{idea} viral adoption potential`
- Invokes Tavily MCP tool for each query concurrently
- Aggregates results and truncates to top 40 hits
- Calls LLM with `research.md` prompt to generate structured `ResearchDossier`
- Transitions to `Phase.PLANNED`

**Key dependency**: `tavily_search` MCP tool (`src/mcp/client.py`)

#### 3. `clarify.py` - User Clarifying
**Purpose**: Human-in-the-loop for ambiguous decisions.

**How it works**:
- Extracts unanswered questions from the research dossier
- Uses `langgraph.types.interrupt()` to pause the graph
- Presents questions to user via API response
- Resumes with user's answers via `Command(resume=answers)`
- Re-enters the node if more questions remain
- If all answered or no questions, transitions to `Phase.PLANNED`

**Pattern**: Conditional edge from graph.py decides whether to re-enter or proceed

#### 4. `analyze.py` - Risk Analysis
**Purpose**: Generate go/no-go scorecard with risk matrix.

**How it works**:
- Receives research dossier and user answers
- Calls LLM with `analyze.md` prompt for structured output
- LLM produces structured `Scorecard` with:
  - `verdict`: "go", "no-go", or "conditional go"
  - `risk_matrix`: Probability/impact scored risks (1-5)
  - `virality_score` and `adoption_score` (0-10)
  - `rationale`: 3-8 sentence justification
- Includes fail-soft error handling to capture LLM failures
- Transitions to `Phase.PLANNED`

#### 5. `write_spec.py` - Specification Generation
**Purpose**: Create HLD/LLD documents with Mermaid diagrams.

**How it works**:
- Receives idea, research, and scorecard
- Calls LLM with `spec.md` prompt for structured output
- LLM produces `Docs` with:
  - `hld`: High-level design (markdown)
  - `lld`: Low-level design with `## Area: <name>` headings
  - `mermaid_hld`: Flowchart of components
  - `mermaid_lld`: Sequence diagram
  - `stack`: Technology recommendations
- Splits LLD into per-area excerpts for ticket generation
- Uses regex-based section extraction in `_split_sections()`
- Transitions to `Phase.SPEC`

#### 6. `publish_notion.py` - Notion Publication
**Purpose**: Best-effort publication of spec to Notion.

**How it works**:
- Checks for Notion MCP tool availability
- **Fail-soft pattern**: If MCP unavailable, logs to console and proceeds
- Converts Docs structure to Notion block format
- Invokes `notion_pages_create` with parent ID from config
- Extracts page ID from various response formats
- Updates state with Notion page reference
- Transitions to `Phase.SPEC` (regardless of Notion success)

#### 7. `generate_tickets.py` - Ticket Generation
**Purpose**: Convert spec into ordered implementation tickets.

**How it works**:
- Calls LLM with `prd.md` and `task_brief.md` prompts
- LLM produces structured `TicketList` (4-8 tickets typically)
- Each ticket has: `title`, `prd`, `acceptance`, `priority`, `area`, `out_of_scope`
- Persists tickets to SQLite via `task_store` service
- Extracts spec excerpt for each ticket's area
- **Best-effort Linear integration**: Creates issues via `issueCreate` MCP tool
- Transitions to `Phase.TASKS`

---

## MCP Integrations

### MCP Manager (`src/mcp/client.py`)

The `MCPManager` class provides a unified interface for all Model Context Protocol integrations. It handles:

1. **OAuth client registration** (PKCE flow) for Notion and Linear
2. **Token management** via `token_store`
3. **Transport configuration** (HTTP headers, Bearer tokens)
4. **Lazy tool resolution** via `get_tool()`

### Available MCP Tools

| Tool | Provider | Auth Method | Use Case |
|------|----------|-------------|----------|
| `tavily_search` | Tavily | API Key or OAuth | Market research |
| `notion_pages_create` | Notion | OAuth (Tier B) | Publish specs |
| `issueCreate` | Linear | OAuth | Create tickets |

### Authentication Flow

**Tavily Search** (API Key authentication):
```
Authorization: Bearer <TAVILY_API_KEY>
# or
X-Tavily-Access-Mode: keyless  # for development
```

**Notion & Linear** (OAuth Tier B flow):
1. User visits `/auth/{server}/login`
2. OAuth client registration with PKCE
3. Authorization code exchange for tokens
4. Tokens stored encrypted in SQLite
5. Tokens refreshed when near expiry

### Code Pattern for MCP Integration

```python
from ..mcp.client import mcp

# Best-effort tool retrieval (fail-soft)
try:
    tool = await mcp.get_tool("notion_pages_create")
except RuntimeError:
    logger.warning("MCP unavailable, continuing locally")
    return {"phase": Phase.SPEC}

# Invoke with logging
result = await mcp.ainvoke_with_logging("notion_pages_create", {...})
```

---

## Services Layer

### LLM Client (`src/services/llm.py`)
Factory for creating OpenAI-compatible LLM clients:
- Supports any OpenAI-compatible API (via `LLM_BASE_URL`)
- Configurable model, temperature, timeout, max tokens
- Returns LangChain Runnable for `.ainvoke()` calls

### Prompt Builder (`src/services/prompt_builder.py`)
Load and cache prompt templates:
- Reads from `prompts/` directory
- Memoized to avoid repeated file reads
- Async-compatible for graph nodes

### Task Store (`src/services/task_store.py`)
SQLite persistence for tickets:
- Async interface with aiosqlite
- Supports task CRUD operations
- Stores task briefs, status, and logs
- SSE streaming for real-time updates

---

## Prompts

The pipeline uses prompt templates stored in `prompts/` directory. Each prompt is designed for structured JSON output via Pydantic models.

### `research.md` - Market Research Dossier

**Purpose**: Convert search results into a decision-ready dossier.

**Key improvements for performance**:
- Explicitly instructs to extract from sources, not lecture from memory
- Requires source attribution for every claim
- Uses numbered steps to ensure comprehensive coverage
- Structured output format for downstream processing

**Output structure**:
```json
{
  "summary": "3-4 sentence opportunity summary",
  "competitors": [{"name", "positioning", "strengths", "weaknesses"}],
  "risks": ["technical risk", "market risk", ...],
  "trends": ["trend 1", "trend 2"],
  "questions": [{"id", "question", "why"}],
  "virality_factors": ["network effect", "sharing loop"]
}
```

### `analyze.md` - Go/No-Go Scorecard

**Purpose**: Generate a defensible go/no-go decision.

**Key improvements for performance**:
- Clear scoring anchors for virality (0-10 bands)
- Clear scoring anchors for adoption (0-10 bands)
- Forces LLM to state limitations when data is thin
- Risk matrix ordered by probability × impact

**Output structure**:
```json
{
  "verdict": "go/no-go/conditional go",
  "risk_matrix": [{"risk", "probability", "impact", "mitigation"}],
  "competitor_overview": "3-5 sentences",
  "virality_score": 0-10,
  "adoption_score": 0-10,
  "rationale": "3-8 sentence justification"
}
```

### `spec.md` - HLD/LLD Generation

**Purpose**: Create implementation-ready design documents.

**Key improvements for performance**:
- Mandates `## Area: <ShortName>` headings for automatic ticket splitting
- Specifies Mermaid diagram formats (flowchart for HLD, sequenceDiagram for LLD)
- Requires concrete technology choices with justifications
- Instructs to name trade-offs rejected

**Output structure**:
```json
{
  "hld": "markdown overview with components and APIs",
  "lld": "markdown with ## Area: headings",
  "mermaid_hld": "flowchart TD/LR",
  "mermaid_lld": "sequenceDiagram",
  "stack": "technology stack with justifications"
}
```

### `prd.md` - Product Requirement Document

**Purpose**: Convert spec into ordered implementation tickets.

**Key improvements for performance**:
- Requires 4-8 tickets (not too many, not too few)
- Mandates dependency-aware ordering
- Enforces clear acceptance criteria with observable conditions
- Separates title (outcome-focused) from PRD (process-focused)

**Output structure**:
```json
{
  "tickets": [
    {
      "title": "5-10 words, outcome-focused",
      "prd": "user story + requirements + context",
      "acceptance": ["criterion 1", "criterion 2"],
      "priority": "high/medium/low",
      "area": "from LLD heading",
      "out_of_scope": "explicit boundaries"
    }
  ]
}
```

### `task_brief.md` - Implementation Brief

**Purpose**: Render task as a paste-into-Claude prompt for AI coding agents.

**Template variables**: `{id}`, `{title}`, `{area}`, `{prd}`, `{criteria}`, `{spec_excerpt}`, `{stack}`, `{out_of_scope}`

**Key improvements for performance**:
- Explicit "How to work this task" instructions
- Acceptance criteria as definition of done
- Spec excerpt limited to 1500 chars for focused context
- Out-of-scope section prevents scope creep

---

## Configuration

Required environment variables (`.env`):

```env
LLM_API_KEY=<your-openai-key>
LLM_MODEL=gpt-4.1-mini
LLM_BASE_URL=https://api.openai.com/v1
OAUTH_REDIRECT_URI=http://localhost:8000/callback
```

Optional:

```env
TAVILY_API_KEY=<your-key>
NOTION_PARENT_DB_ID=<database-id>
```

Database location: `.puding/db/` (auto-created)

---

## Testing

Run tests with:

```bash
uv run pytest tests/ -v
```

---

## Development

### CLI Usage

```bash
# Run the pipeline
uv run puding

# With verbose logging
uv run puding -v
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

### Development Server

```bash
uv sync --extra dev
uv run dev-server  # Navigate to http://127.0.0.1:8000/docs
```

---

## Domain Glossary

| Term | Description |
|------|-------------|
| **Idea** | Raw product concept from user input |
| **Research** | Market analysis from search results |
| **Dossier** | Structured research output (summary, competitors, risks, etc.) |
| **Clarification** | User answers to open questions |
| **Scorecard** | Go/no-go decision with risk matrix |
| **Spec** | High-level and low-level design documents |
| **Ticket** | Implementation task for an engineer |
| **Thread** | Conversation context identified by `thread_id` |

---

## Integration Points

### MCP Servers Summary

| Server | Tools | Authentication | Status |
|--------|-------|----------------|--------|
| Tavily | `tavily_search` | API Key (or keyless dev mode) | ✅ Required |
| Notion | `notion_pages_create` | OAuth Tier B | ✅ Optional (best-effort) |
| Linear | `issueCreate` | OAuth Tier B | ✅ Optional (best-effort) |

### OAuth Flow

For Notion and Linear, users must complete OAuth:

1. Visit `/auth/{server}/login` to register
2. Complete authorization with the service
3. Tokens are stored in `.puding/db/tokens.db`

### Linear Project

This repository is attached to the **Metis** project in Linear:

- **Project**: [Metis (P-SHIP-3)](https://linear.app/heimdallabs/project/metis-5864eaf29689)
- **Team**: Ship (SHIP)
- **Lead**: Sagar Bera
- **Repo link**: https://github.com/sagarbera/puding

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

- [prompts/](prompts/) - LLM prompt templates
- [.env.example](.env) - Environment configuration template
- [src/graph.py](src/graph.py) - State machine builder
- [src/types.py](src/types.py) - Domain types and Pydantic models