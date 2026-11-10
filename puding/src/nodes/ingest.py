import logging

from ..types import Phase, ProductState

logger = logging.getLogger(__name__)


def ingest(state: ProductState) -> ProductState:
    """Extract and normalize the incoming idea."""
    logger.debug("INGEST: Starting ingestion")
    idea = state.get("idea", "").strip()
    logger.debug("INGEST: Idea extracted, length=%d", len(idea))
    result: ProductState = {"phase": Phase.IDEA, "idea": idea}
    logger.debug("INGEST: Completed, returning phase=IDEA")
    return result
