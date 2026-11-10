from __future__ import annotations

import logging

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .config import DB_DIR
from .nodes.analyze import analyze
from .nodes.clarify import clarify
from .nodes.generate_tickets import generate_tickets
from .nodes.ingest import ingest
from .nodes.publish_notion import publish_notion
from .nodes.research import research
from .nodes.write_spec import write_spec
from .types import ProductState

STATE_DB = DB_DIR / "state.db"
logger = logging.getLogger(__name__)


async def build_graph() -> tuple[
    CompiledStateGraph[ProductState], aiosqlite.Connection
]:
    logger.debug("GRAPH: Building LangGraph state machine")
    # Async SQLite checkpointer — durable across restarts
    logger.debug("GRAPH: Connecting to SQLite checkpointer at %s", STATE_DB)
    conn = await aiosqlite.connect(STATE_DB, check_same_thread=False)
    # Explicitly allow our Phase enum in checkpoint deserialization
    # (otherwise langgraph emits an "unregistered type" warning).
    serde = JsonPlusSerializer(allowed_msgpack_modules=[("src.types", "Phase")])
    checkpointer = AsyncSqliteSaver(conn, serde=serde)
    logger.debug("GRAPH: Setting up checkpointer tables")
    await checkpointer.setup()  # create tables

    g = StateGraph(ProductState)
    nodes = [
        ingest,
        research,
        clarify,
        analyze,
        write_spec,
        publish_notion,
        generate_tickets,
    ]
    for node in nodes:
        g.add_node(node.__name__, node)
        logger.debug("GRAPH: Added node '%s'", node.__name__)
    g.add_edge(START, "ingest")
    g.add_edge("ingest", "research")
    g.add_edge("research", "clarify")
    g.add_conditional_edges(
        "clarify",
        lambda s: "clarify" if s.get("pending_questions") else "analyze",
        {"clarify": "clarify", "analyze": "analyze"},
    )
    g.add_edge("analyze", "write_spec")
    g.add_edge("write_spec", "publish_notion")
    g.add_edge("publish_notion", "generate_tickets")
    g.add_edge("generate_tickets", END)

    logger.debug("GRAPH: Compiling graph")
    compiled = g.compile(checkpointer=checkpointer)
    return compiled, conn


async def pending_questions(result) -> list[dict]:
    """Extract pending clarification questions from an invoke() result."""
    logger.debug("PENDING_QUESTIONS: Extracting pending questions from result")
    if not isinstance(result, dict):
        logger.debug("PENDING_QUESTIONS: Result is not a dict, returning []")
        return []
    for key in ("interrupts", "__interrupt__"):
        if key in result:
            vals = result[key]
            if isinstance(vals, list) and vals:
                first = vals[0]
                # Interrupt objects have a .value attribute; older dict format also supported
                if hasattr(first, "value"):
                    payload = first.value or {}
                elif isinstance(first, dict):
                    payload = first.get("value", {})
                else:
                    payload = {}
                qs = payload.get("questions", [])
                logger.debug(
                    "PENDING_QUESTIONS: Found %d questions in '%s'", len(qs), key
                )
                return qs
    logger.debug("PENDING_QUESTIONS: No pending questions found")
    return []
