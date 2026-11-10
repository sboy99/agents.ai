import logging
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from ..graph import build_graph, pending_questions
from ..types import Phase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ideas", tags=["ideas"])


class IdeaIn(BaseModel):
    idea: str


class AnswersIn(BaseModel):
    answers: list[dict]


@router.post("")
async def start_idea(payload: IdeaIn):
    logger.debug(
        "IDEAS: start_idea called with idea=%s",
        payload.idea[:50] + "..." if len(payload.idea) > 50 else payload.idea,
    )
    tid = uuid.uuid4().hex
    logger.debug("IDEAS: Generated thread_id=%s", tid)
    agent, conn = await build_graph()
    logger.debug("IDEAS: Built LangGraph agent")
    result = await agent.ainvoke(
        {"phase": Phase.IDEA, "idea": payload.idea},
        config={"configurable": {"thread_id": tid}},
    )
    logger.debug("IDEAS: Agent invoked, checking for pending questions")
    qs = await pending_questions(result)
    logger.debug("IDEAS: Found %d pending questions", len(qs))
    await conn.close()
    return {"thread_id": tid, "needs_input": bool(qs), "questions": qs}
