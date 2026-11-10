"""Human-in-the-loop: pauses the graph to ask the user clarifying questions."""

import logging

from langgraph.types import interrupt

from ..types import Phase, ProductState
from .logging_utils import log_phase

logger = logging.getLogger(__name__)


async def clarify(state: ProductState) -> ProductState:
    logger.debug("CLARIFY: Starting clarification phase")
    answered = state.get("answers", {})

    # Only questions not yet answered
    pending = [
        q
        for q in state.get("research", {}).get("questions", [])
        if q["id"] not in answered
    ]
    logger.debug("CLARIFY: Pending questions count: %d", len(pending))

    # No questions left → move to analyze
    if not pending:
        logger.debug("CLARIFY: No pending questions, proceeding to analyze")
        return {"pending_questions": [], "phase": Phase.PLANNED}

    log_phase("Clarify", f"Asking {len(pending)} clarifying questions")
    logger.debug("CLARIFY: Sending %d questions to user via interrupt", len(pending))
    # GRAPH PAUSES HERE. The API/CLI resumes with the user's answers.
    replies = interrupt({"type": "clarification", "questions": pending})

    # Merge answers (only ones matching a real question id)
    new_answers = {}
    for rep in replies or []:
        if (
            rep.get("id")
            and rep.get("answer")
            and any(q["id"] == rep["id"] for q in pending)
        ):
            new_answers[rep["id"]] = rep["answer"].strip()

    merged = {**answered, **new_answers}
    still = [q for q in pending if q["id"] not in merged]
    logger.debug("CLARIFY: Merged answers, still pending: %d", len(still))
    return {"answers": merged, "pending_questions": still}
