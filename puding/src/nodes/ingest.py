import logging

from ..types import Phase, ProductState
from .logging_utils import log_phase

logger = logging.getLogger(__name__)


def ingest(state: ProductState) -> ProductState:
    """Extract and normalize the incoming idea."""
    log_phase("Ingest", f"Processing idea: '{state.get('idea', '')[:50]}...'")
    logger.debug("INGEST: Starting ingestion")
    idea = state.get("idea", "").strip()
    logger.debug("INGEST: Idea extracted, length=%d", len(idea))
    result: ProductState = {"phase": Phase.IDEA, "idea": idea}
    logger.debug("INGEST: Completed, returning phase=IDEA")
    return result
