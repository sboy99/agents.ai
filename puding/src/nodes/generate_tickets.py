import json
import logging
from typing import cast

from langchain_core.tools import ToolException
from langgraph.config import get_config

from ..mcp.client import mcp
from ..services.llm import get_llm
from ..services.prompt_builder import load_prompt
from ..services.task_store import task_store
from ..types import Phase, ProductState, TicketList
from .logging_utils import log_phase

logger = logging.getLogger(__name__)


def _excerpt_for(lld: str, area: str) -> str:
    """Extract a section from LLD matching the area."""
    if not lld:
        return ""
    lines = lld.splitlines()
    capturing = False
    excerpt_lines = []

    for line in lines:
        if line.startswith("#"):
            heading = line.lstrip("#").strip().lower()
            if area.lower() in heading or heading in area.lower():
                capturing = True
                excerpt_lines.append(line)
                continue
            elif capturing:
                break
        if capturing:
            excerpt_lines.append(line)

    if not excerpt_lines:
        return lld[:1000]
    return "\n".join(excerpt_lines)


async def generate_tickets(state: ProductState) -> ProductState:
    log_phase("Tickets", "Generating implementation tickets")
    logger.debug("GENERATE_TICKETS: Starting ticket generation")
    llm = get_llm()
    logger.debug("GENERATE_TICKETS: Calling LLM with structured output for TicketList")
    parsed = cast(
        TicketList,
        await llm.with_structured_output(TicketList).ainvoke(
            [
                {"role": "system", "content": load_prompt("prd.md")},
                {"role": "user", "content": json.dumps(state.get("docs", {}))},
            ]
        ),
    )
    logger.debug("GENERATE_TICKETS: Received %d tickets from LLM", len(parsed.tickets))

    docs = state.get("docs", {})
    lld = docs.get("lld") or docs.get("hld") or ""

    tickets = []
    for i, t in enumerate(parsed.tickets, 1):
        tickets.append(
            {
                **t.model_dump(),
                "identifier": f"TASK-{i:03d}",
                "status": "todo",
                "spec_excerpt": _excerpt_for(lld, t.area),
            }
        )
    logger.debug("GENERATE_TICKETS: Built %d ticket dicts", len(tickets))

    # Persist to the async task store
    config = get_config()
    configurable = config.get("configurable", {}) if config else {}
    thread_id = configurable.get("thread_id")
    if not thread_id:
        raise ValueError("thread_id is required in config")
    logger.debug(
        "GENERATE_TICKETS: Persisting tickets to task_store for thread_id=%s", thread_id
    )
    await task_store.create_many(thread_id, tickets)
    logger.debug("GENERATE_TICKETS: Tickets persisted to local DB")

    # Create in Linear via MCP (best-effort; don't fail the graph)
    issue_create = None
    try:
        issue_create = await mcp.get_tool("issueCreate")
        logger.debug("GENERATE_TICKETS: Retrieved issueCreate tool from MCP")
    except RuntimeError as exc:
        logger.warning("GENERATE_TICKETS: Linear MCP unavailable: %s", exc)
        # Log the LLM response (tickets) when tool is not found
        logger.info(
            "GENERATE_TICKETS: Logging LLM response, not connecting to Linear MCP\n%s",
            json.dumps(tickets, indent=2)[:10000],
        )

    if issue_create:
        logger.debug("GENERATE_TICKETS: Creating %d issues in Linear", len(tickets))
        for ticket in tickets:
            try:
                await mcp.ainvoke_with_logging(
                    "issueCreate",
                    {"title": ticket["title"], "description": ticket["prd"]},
                )
                logger.debug(
                    "GENERATE_TICKETS: Created Linear issue %s", ticket["identifier"]
                )
            except (RuntimeError, ToolException, ValueError) as exc:
                logger.warning(
                    "GENERATE_TICKETS: Linear create failed for %s: %s",
                    ticket["identifier"],
                    exc,
                )

    logger.debug("GENERATE_TICKETS: Completed, moving to PHASE.TASKS")
    return {"tickets": tickets, "phase": Phase.TASKS}
