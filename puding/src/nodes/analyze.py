"""Turn research + user answers into a go/no-go scorecard."""

import json
import logging
from typing import cast

from ..services.llm import get_llm
from ..services.prompt_builder import load_prompt
from ..types import Phase, ProductState, Scorecard
from .logging_utils import log_phase

logger = logging.getLogger(__name__)


async def analyze(state: ProductState) -> ProductState:
    log_phase("Analysis", "Risk scoring and go/no-go decision")
    logger.debug("ANALYZE: Starting analysis phase")
    if not state.get("research"):
        logger.debug("ANALYZE: No research data found, returning empty scorecard")
        return {"scorecard": {}, "phase": Phase.PLANNED}

    llm = get_llm()
    logger.debug("ANALYZE: Calling LLM with structured output for Scorecard")

    try:
        card = cast(
            Scorecard,
            await llm.with_structured_output(Scorecard).ainvoke(
                [
                    {"role": "system", "content": load_prompt("analyze.md")},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "idea": state.get("idea", ""),
                                "research": state.get("research"),
                                "answers": state.get("answers", {}),
                            }
                        ),
                    },
                ]
            ),
        )
        logger.debug(
            "ANALYZE: Scorecard generated successfully, verdict=%s", card.verdict
        )
    except Exception as exc:  # noqa: BLE001 - fail soft, surface error to API
        # Fail soft: record the error so the API can surface it
        logger.warning("ANALYZE: LLM call failed: %s", exc)
        return {
            "scorecard": {"verdict": f"Analysis failed: {exc}"},
            "phase": Phase.PLANNED,
        }

    return {"scorecard": card.model_dump(), "phase": Phase.PLANNED}
