# Pudding Glossary

Domain terms for the Idea-to-Implementation Pipeline.

## Core Concepts

### Idea
A raw product concept or feature request entered by the user. The starting point of the pipeline.

### Research Dossier
Structured market research output containing:
- Summary of opportunity
- Competitor analysis
- Risk matrix
- Market trends
- Open questions requiring user input
- Virality factors

### Clarification
User-provided answers to open questions that emerged during research. The pipeline may pause at this step via LangGraph interrupt points.

### Scorecard
Go/no-go decision document with:
- Verdict (`go`, `no-go`, or `conditional go`)
- Risk matrix with probability/impact scores
- Competitor overview
- Virality and adoption scores (0-10)
- Rationale

### Spec (Specification)
Design document containing:
- HLD (High-Level Design) - Architecture overview
- LLD (Low-Level Design) - Detailed implementation
- Mermaid diagrams (HLD and LLD)

### Ticket
An implementation task for an engineer with:
- Title
- PRD (Product Requirements Document)
- Acceptance criteria
- Priority
- Area
- Spec excerpt

### Phase
The current stage of the pipeline. Values:
- `IDEA` - Initial ingestion
- `PLANNED` - Ready for next stage (post-research/analysis)
- `SPEC` - Spec generated
- `TASKS` - Tickets generated

### Thread
A conversation context identified by `thread_id`. Contains the state of a single idea through the pipeline.

## Integration Points

### MCP (Model Context Protocol)
Protocol for tools that provide external capabilities:
- **Tavily Search** - Web search for research phase
- **Notion Pages** - Publication destination for specs
- **Linear Issues** - Ticket creation destination

### OAuth Flow
Tier B OAuth for MCP servers:
1. User visits `/auth/{server}/login`
2. Completes authorization at the provider
3. Callback stores credentials in TokenStore

## Architecture Terms

### Seam
A place where the MCP client or auth module interfaces with external services. The interface is at the seam; implementation details are hidden behind it.

### Adapter
Concrete implementations at seams:
- `MCPManager` → MultiServerMCPClient
- `OAuthClient` → OAuth authorization flow
- `TaskStore` → SQLite persistence

### Pipeline
The LangGraph state machine connecting nodes:
```
ingest → research → clarify → analyze → write_spec → publish_notion → generate_tickets
```

## Key Terminology for This Codebase

- **Ingest module**: `src/nodes/ingest.py` - Normalizes user input
- **Research module**: `src/nodes/research.py` - Performs market research
- **Clarify module**: `src/nodes/clarify.py` - Handles user interruptions
- **Analyze module**: `src/nodes/analyze.py` - Produces go/no-go scorecard
- **Write Spec module**: `src/nodes/write_spec.py` - Generates HLD/LLD
- **Publish Notion module**: `src/nodes/publish_notion.py` - Best-effort Notion publish
- **Generate Tickets module**: `src/nodes/generate_tickets.py` - Creates implementation tickets