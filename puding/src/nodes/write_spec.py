"""Generate HLD + LLD + Mermaid diagrams, and split LLD into per-area excerpts."""

import json
import logging
import re
from typing import cast

from ..services.llm import get_llm
from ..services.prompt_builder import load_prompt
from ..types import Docs, Phase, ProductState
from .logging_utils import log_phase

logger = logging.getLogger(__name__)


async def write_spec(state: ProductState) -> ProductState:
    log_phase("Spec", "Generating HLD/LLD with Mermaid diagrams")
    logger.debug("WRITE_SPEC: Starting spec generation phase")
    llm = get_llm()

    try:
        docs = cast(
            Docs,
            await llm.with_structured_output(Docs).ainvoke(
                [
                    {"role": "system", "content": load_prompt("spec.md")},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "idea": state.get("idea", ""),
                                "research": state.get("research"),
                                "scorecard": state.get("scorecard", {}),
                            }
                        ),
                    },
                ]
            ),
        )
        logger.debug("WRITE_SPEC: Docs generated successfully")
    except Exception as exc:  # noqa: BLE001 - fail soft, surface error to API
        logger.warning("WRITE_SPEC: LLM call failed: %s", exc)
        return {"docs": {}, "phase": Phase.SPEC}

    d = docs.model_dump()

    # Split the LLD into per-area excerpts for ticket briefs.
    # Assume LLD uses '## Area: <name>' or '## <name>' (heading level 2).
    d["sections"] = _split_sections(d.get("lld", ""))
    logger.debug("WRITE_SPEC: Split into %d sections", len(d["sections"]))

    return {"docs": d, "phase": Phase.SPEC}


def _split_sections(lld: str) -> dict[str, str]:
    """Return {area_name: excerpt} from the LLD markdown.

    Falls back to a single 'core' section containing the whole LLD if no
    '## ' headings are found (or the LLM used a different heading style).
    """
    lines = lld.splitlines()
    headings = [
        (i, line.strip().lstrip("#").strip())
        for i, line in enumerate(lines)
        if re.match(r"^##\s+", line)
    ]
    if not headings:
        return {"core": lld.strip()}

    sections = {}
    for idx, (start, name) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        sections[name.lower()] = "\n".join(lines[start:end]).strip()
    return sections
