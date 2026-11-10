# Pudding Tasks & Roadmap

This document summarizes the execution tasks and tickets for Pudding progress streaming and MCP fallback handling.

---

## Part 1: CLI Progress Streaming Engine (T01 – T08)

The tracer-bullet implementation tasks for streaming model progress and thinking status to the CLI.

### T01: Core CLI Streaming Engine
- **Area:** Core Streaming
- **Description:** Implement `ProgressEvent` schema, `ProgressBus` (with `ContextVar` context management), `@traced` decorator for graph nodes, and `run_pipeline` pump-and-drain loop.
- **Key Files:** `src/services/progress.py`, `src/nodes/traced.py`, `src/cli/stream.py`, `src/cli/renderer.py`, `src/puding/__init__.py`
- **Status:** In Progress / Ready for Implementation

### T02: Rich Terminal Renderer
- **Area:** CLI UX
- **Description:** Add terminal formatting, phase status spinners, and phase transition visuals.
- **Key Files:** `src/cli/renderer.py`
- **Status:** Pending T01

### T03: Detailed Sub-Events for Research
- **Area:** Nodes / Research
- **Description:** Emit real-time sub-events during search query execution and dossier assembly.
- **Key Files:** `src/nodes/research.py`
- **Status:** Pending T01

### T04: Clarification Pause & Resume
- **Area:** CLI / Graph
- **Description:** Integrate LangGraph `interrupt` questions seamlessly into the streaming loop and support answer submission.
- **Key Files:** `src/nodes/clarify.py`, `src/cli/stream.py`
- **Status:** Pending T01

### T05: Per-Ticket Progressive Sync Event
- **Area:** Nodes / Tickets
- **Description:** Refactor `generate_tickets` to emit events per ticket as generated and persisted.
- **Key Files:** `src/nodes/generate_tickets.py`
- **Status:** Pending T01

### T06: Notion Publishing Status Event
- **Area:** Nodes / Notion
- **Description:** Emit events tracking Notion page creation start, success, or fallback.
- **Key Files:** `src/nodes/publish_notion.py`
- **Status:** Pending T01

### T07: Fail-Soft & Verdict Reporting
- **Area:** Nodes / Analysis
- **Description:** Emit structured scorecard analysis events and fail-soft error notices.
- **Key Files:** `src/nodes/analyze.py`
- **Status:** Pending T01

### T08: Verbose Token Streaming & Configuration
- **Area:** Config / LLM
- **Description:** Add `--stream` and `--verbose` flags, and hook LangChain callbacks to stream raw reasoning/LLM tokens when enabled.
- **Key Files:** `src/config.py`, `src/services/llm.py`, `src/puding/__init__.py`
- **Status:** Pending T01

---

## Part 2: Progressive Output & MCP Integration Tickets

Detailed tickets for progressive output and handling scenarios where MCP servers (Linear, Notion) are unavailable.

### Ticket 1: Add SSE Streaming Endpoint for Tasks
- **Priority:** High | **Area:** API
- **Title:** Add Server-Sent Events endpoint for task streaming
- **Description:** Create `GET /tasks/stream/{thread_id}` using SSE to stream ticket data to API clients in real time.

### Ticket 2: Refactor Generate Tickets for Incremental Output
- **Priority:** High | **Area:** Tickets
- **Title:** Refactor ticket generation to support incremental streaming
- **Description:** Yield tickets incrementally during generation, persist each immediately to SQLite, and update state progressively.

### Ticket 3: Add Linear Issue Creation Status Tracking
- **Priority:** Medium | **Area:** Integrations
- **Title:** Track Linear issue creation status per ticket
- **Description:** Track `linear_issue_id` and `creation_status` (`pending`, `success`, `failed`, `local_only`) per ticket.

### Ticket 4: Update CLI for Progress Display
- **Priority:** Medium | **Area:** CLI
- **Title:** Update CLI to display progressive ticket generation output
- **Description:** Consume streaming events in CLI and show live progress counters and Linear sync status.

### Ticket 5: Improve MCP Unavailability Handling
- **Priority:** Medium | **Area:** Error Handling
- **Title:** Improve error messaging and fallback behavior when MCP is unavailable
- **Description:** Provide clear console guidance and ensure tickets and specs are stored locally when MCP servers are offline.

### Ticket 6: Add Notion Database Schema Documentation
- **Priority:** Low | **Area:** Documentation
- **Title:** Document Notion integration requirements and schema
- **Description:** Write setup guides for Notion OAuth, page hierarchies, and required database properties.
