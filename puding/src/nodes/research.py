import asyncio
import json
import logging
from typing import Any, cast

from ..mcp.client import mcp
from ..services.llm import get_llm
from ..services.prompt_builder import load_prompt
from ..types import Phase, ProductState, ResearchDossier
from .logging_utils import log_mcp_tool_call, log_phase

logger = logging.getLogger(__name__)


def _extract_results(resp: Any) -> list:
    """Extract search result dicts from an MCP tool response.

    langchain-mcp-adapters tools return a list of LangChain content blocks,
    e.g. [{"type": "text", "text": '{"query": ..., "results": [...]}'}].
    This handles that shape as well as a plain list of results, a
    {"results": [...]} dict, or a (content, artifact) tuple.
    """
    # Unpack (content, artifact) tuple form
    if isinstance(resp, tuple) and resp:
        resp = resp[0]

    # Plain {"results": [...]} dict form
    if isinstance(resp, dict):
        results = resp.get("results")
        return results if isinstance(results, list) else []

    if not isinstance(resp, list):
        return []

    out: list = []
    for block in resp:
        # Content block whose "text" is a JSON payload
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            try:
                parsed = json.loads(block["text"])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and isinstance(parsed.get("results"), list):
                out.extend(parsed["results"])
            elif isinstance(parsed, list):
                out.extend(parsed)
        # Already a bare result dict
        elif isinstance(block, dict):
            out.append(block)
    return out


async def research(state: ProductState) -> ProductState:
    log_phase("Research", "Market research via Tavily search")
    logger.debug("RESEARCH: Starting research phase")
    idea = state.get("idea", "")
    queries = [
        f"{idea} market competitors",
        f"{idea} existing products alternatives",
        f"{idea} risks challenges regulation",
        f"{idea} viral adoption potential",
    ]
    logger.debug("RESEARCH: Built %d search queries", len(queries))
    for q in queries:
        logger.debug("RESEARCH: Query: %s", q)

    async def run(q) -> list:
        log_mcp_tool_call("tavily_search", {"query": q, "max_results": 4})
        resp = await mcp.ainvoke_with_logging(
            "tavily_search", {"query": q, "max_results": 4}
        )
        results = _extract_results(resp)
        logger.debug("RESEARCH: Query '%s' returned %d results", q, len(results))
        return results

    results = await asyncio.gather(*(run(q) for q in queries), return_exceptions=True)
    hits: list = []
    for r in results:
        if isinstance(r, BaseException):
            logger.warning("RESEARCH: Search query failed: %s", r)
        else:
            hits.extend(r)
    logger.debug("RESEARCH: Total hits collected: %d", len(hits))

    llm = get_llm()
    dossier = cast(
        ResearchDossier,
        await llm.with_structured_output(ResearchDossier).ainvoke(
            [
                {"role": "system", "content": load_prompt("research.md")},
                {
                    "role": "user",
                    "content": json.dumps({"idea": idea, "sources": hits[:40]}),
                },
            ]
        ),
    )
    logger.debug("RESEARCH: Dossier generated, moving to PHASE.PLANNED")
    return {"research": dossier.model_dump(), "phase": Phase.PLANNED}
