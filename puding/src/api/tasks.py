import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.prompt_builder import load_prompt
from ..services.task_store import task_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


class MoveIn(BaseModel):
    status: Literal["todo", "in_progress", "done"]


def brief_from_row(row: dict) -> str:
    """Render the paste-into-Claude prompt from a stored task row."""
    return load_prompt("task_brief.md").format(
        id=row["identifier"],
        title=row["title"],
        prd=row["prd"],
        criteria="\n".join(f"- {c}" for c in row["acceptance"]),
        area=row["area"],
        spec_excerpt=(row.get("spec_excerpt") or "")[:1500],
        stack="LangGraph, FastAPI, Python 3.11+, MCP (langchain-mcp-adapters)",
        out_of_scope=row.get("out_of_scope", "unrelated modules"),
    )


@router.get("")
async def list_tasks(thread_id: str = Query(...)):
    logger.debug("TASKS: GET /tasks - thread_id=%s", thread_id)
    return {"tasks": await task_store.list_by_thread(thread_id)}


@router.get("/current")
async def current_task(thread_id: str = Query(...), include_brief: bool = True):
    logger.debug(
        "TASKS: GET /tasks/current - thread_id=%s, include_brief=%s",
        thread_id,
        include_brief,
    )
    row = await task_store.current_for_thread(thread_id)
    if not row:
        logger.debug("TASKS: No open task found for thread %s", thread_id)
        return {
            "task": None,
            "prompt": "No open task — run a new idea through the pipeline.",
        }
    logger.debug("TASKS: Found current task %s", row["identifier"])
    return {"task": row, "prompt": brief_from_row(row) if include_brief else None}


@router.get("/{identifier}")
async def get_task(identifier: str, thread_id: str = Query(...)):
    logger.debug("TASKS: GET /tasks/%s - thread_id=%s", identifier, thread_id)
    row = await task_store.get(thread_id, identifier)
    if not row:
        logger.debug("TASKS: Task %s not found", identifier)
        raise HTTPException(404, f"Task {identifier} not found")
    return row


@router.get("/{identifier}/brief")
async def task_brief(identifier: str, thread_id: str = Query(...)):
    logger.debug("TASKS: GET /tasks/%s/brief - thread_id=%s", identifier, thread_id)
    row = await task_store.get(thread_id, identifier)
    if not row:
        logger.debug("TASKS: Task %s not found", identifier)
        raise HTTPException(404, f"Task {identifier} not found")
    return {"task": row, "prompt": brief_from_row(row)}


@router.post("/{identifier}/move")
async def move_task(identifier: str, payload: MoveIn, thread_id: str = Query(...)):
    logger.debug(
        "TASKS: POST /tasks/%s/move - thread_id=%s, status=%s",
        identifier,
        thread_id,
        payload.status,
    )
    """Transition status: todo -> in_progress -> done."""
    updated = await task_store.update_status(thread_id, identifier, payload.status)
    if not updated:
        logger.debug("TASKS: Task %s not found for move", identifier)
        raise HTTPException(404, f"Task {identifier} not found")
    logger.debug("TASKS: Task %s status updated to %s", identifier, payload.status)
    return {"task": updated}


@router.get("/{identifier}/logs")
async def get_task_logs(identifier: str, thread_id: str = Query(...), limit: int = 100):
    """Get recent logs for a task (polling fallback)."""
    logger.debug(
        "TASKS: GET /tasks/%s/logs - thread_id=%s, limit=%s",
        identifier,
        thread_id,
        limit,
    )
    return {"logs": await task_store.get_logs(thread_id, limit)}


@router.get("/stream/{thread_id}")
async def stream_task_logs(request: Request, thread_id: str = Query(...)):
    """Stream logs for a thread as Server-Sent Events.

    Usage:
        curl -N http://localhost:8000/tasks/stream/{thread_id}
    """
    logger.debug("TASKS: GET /tasks/stream/%s - thread_id=%s", "stream", thread_id)

    async def event_generator():
        try:
            async for sse in task_store.stream_logs(thread_id):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.debug(
                        "TASKS: Client disconnected from stream for thread_id=%s",
                        thread_id,
                    )
                    break
                yield sse
        except asyncio.CancelledError:
            # Client disconnected, no need to log
            raise
        except (ValueError, OSError, RuntimeError) as e:
            # Log common error types for debugging
            logger.warning("TASKS: Stream error for thread_id=%s: %s", thread_id, e)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
