import json
import logging
from typing import Any

from ..mcp.client import mcp
from ..types import Docs, Phase, ProductState
from .logging_utils import log_phase

logger = logging.getLogger(__name__)


def _block_for(docs: dict) -> dict:
    """Convert Docs to a Notion block structure."""
    d = Docs.model_validate(docs) if isinstance(docs, dict) else docs
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"type": "text", "text": {"content": d.hld}},
            ],
        },
    }


def _extract_page_id(resp: Any) -> str | None:
    """Extract the page ID from a Notion tool response.

    MCP tools with response_format="content_and_artifact" return a tuple
    (content, artifact). The content is a list of content blocks, and
    the artifact may contain structured content.
    """
    # If response is a string, return it directly
    if isinstance(resp, str):
        return resp

    # If response is a tuple (content, artifact), extract from content
    if isinstance(resp, tuple) and len(resp) >= 1:
        content = resp[0]

        # Content is a list of content blocks
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    # Try to extract page ID from text
                    if isinstance(text, str):
                        return text.strip() if text else None
            return None

        # Single content item
        return content if isinstance(content, str) else None

    # If response is a dict, try to extract page ID
    if isinstance(resp, dict):
        return resp.get("page_id") or resp.get("id")

    return None


async def publish_notion(state: ProductState) -> ProductState:
    log_phase("Notion", "Publishing spec to Notion")
    logger.debug("PUBLISH_NOTION: Starting Notion publication")
    # Best-effort Notion publish; don't fail the graph if MCP unavailable
    try:
        create_page = await mcp.get_tool("notion_pages_create")
        logger.debug("PUBLISH_NOTION: Retrieved notion_pages_create tool")
    except RuntimeError as exc:
        logger.warning("PUBLISH_NOTION: Notion MCP unavailable: %s", exc)
        # Log the LLM response (docs) when tool is not found
        logger.info(
            "PUBLISH_NOTION: Logging LLM response, not connecting to Notion MCP\n%s",
            json.dumps(state.get("docs", {}), indent=2)[:10000],
        )
        return {"phase": Phase.SPEC}

    logger.debug("PUBLISH_NOTION: Invoking notion_pages_create")
    page_id = await create_page.ainvoke(
        {
            "parent_id": state.get("notion_parent_id"),
            "title": state.get("idea", ""),
            "content": [_block_for(state.get("docs", {}))],
        }
    )
    page_id = _extract_page_id(page_id)
    logger.debug("PUBLISH_NOTION: Published page, id=%s", page_id)
    return {"notion_parent_id": page_id, "phase": Phase.SPEC}
