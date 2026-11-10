"""Pipeline streaming pump-and-drain loop for CLI execution.

Provides run_pipeline() which executes the LangGraph pipeline with
real-time progress event streaming to a listener.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from contextvars import ContextVar

from ..graph import build_graph
from ..services.progress import ProgressBus, ProgressEvent, emit_phase_start
from ..types import Phase, ProductState

logger = logging.getLogger(__name__)

# Context var for progress bus state
_progress_bus_ctx: ContextVar[ProgressBus | None] = ContextVar(
    "progress_bus_ctx", default=None
)


async def run_pipeline(
    idea: str,
    event_listener: AsyncIterator[ProgressEvent] | None = None,
    initial_state: dict | None = None,
    thread_id: str | None = None,
) -> ProductState:
    """Run the pudding pipeline with optional progress event streaming.

    Implements a pump-and-drain loop:
    1. Build the graph and create a progress bus
    2. Invoke the pipeline, which emits events via @traced or manually
    3. Pump events from the bus to the listener (if provided)
    4. Drain remaining events at completion

    Args:
        idea: The initial idea string to process
        event_listener: Async iterator that receives progress events
                       (e.g., CLI rendering loop)
        initial_state: Optional pre-populated state dict
        thread_id: Optional thread ID for persistence

    Returns:
        The final pipeline state after all phases complete

    Example:
        async for event in event_listener:
            print(f"{event.phase}: {event.message}")
    """
    # Initialize state
    state: ProductState = initial_state or {"idea": idea, "phase": Phase.IDEA}  # type: ignore[assignment]

    # Create progress bus and set it in context
    bus = ProgressBus.set_current()
    _progress_bus_ctx.set(bus)

    # Generate thread_id if not provided
    if not thread_id:
        thread_id = uuid.uuid4().hex

    # Emit initial event
    await emit_phase_start("ingest", f"Processing idea: {idea[:50]}...")

    # Build the LangGraph agent
    agent, conn = await build_graph()

    try:
        # Pump: Invoke the pipeline through all phases
        # The graph handles phase transitions automatically
        result = await agent.ainvoke(
            state, config={"configurable": {"thread_id": thread_id}}
        )  # type: ignore[arg-type,return-value]

        # Continue through phases until we reach TASKS
        while result.get("phase") != Phase.TASKS:
            result = await agent.ainvoke(  # type: ignore[arg-type,return-value]
                result,  # type: ignore[arg-type]
                config={"configurable": {"thread_id": thread_id}},  # type: ignore[arg-type]
            )

        # Drain remaining events from the bus
        remaining = await bus.drain()
        for event in remaining:
            logger.debug("PIPELINE DRAIN: %s - %s", event.phase, event.message)

        return result  # type: ignore[return-value]

    finally:
        # Clean up the database connection
        await conn.close()
        # Reset bus context
        _progress_bus_ctx.set(None)


async def stream_pipeline(
    idea: str,
    output_handler: Callable[[ProgressEvent], None] | None = None,
    thread_id: str | None = None,
) -> AsyncIterator[ProgressEvent]:
    """Stream pipeline execution as an async iterator of events.

    Convenience wrapper that runs the pipeline and yields events
    as they occur.

    Args:
        idea: The initial idea string to process
        output_handler: Optional callable (sync or async) to process each event
        thread_id: Optional thread ID for persistence

    Yields:
        ProgressEvent objects as they are emitted
    """
    bus = ProgressBus.set_current()
    queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()

    async def emit_to_queue(event: ProgressEvent):
        await queue.put(event)
        if output_handler:
            try:
                if asyncio.iscoroutinefunction(output_handler):
                    await output_handler(event)
                else:
                    output_handler(event)
            except Exception as e:  # noqa: BLE001
                logger.warning("STREAM_HANDLER: Failed: %s", e)

    # Store original emit and create patched version
    original_emit = bus.emit

    def patched_emit(event: ProgressEvent) -> None:
        # Schedule async emit_to_queue without blocking
        asyncio.create_task(emit_to_queue(event))
        original_emit(event)

    # Patch the bus's emit method
    bus.emit = patched_emit

    # Generate thread_id if not provided
    if not thread_id:
        thread_id = uuid.uuid4().hex

    # Initialize state
    state: ProductState = {"idea": idea, "phase": Phase.IDEA}  # type: ignore[assignment]

    # Build the LangGraph agent
    agent, conn = await build_graph()

    try:
        # Emit initial event before starting pipeline
        await emit_phase_start("ingest", f"Processing idea: {idea[:50]}...")

        # Invoke the pipeline through all phases
        result = await agent.ainvoke(
            state, config={"configurable": {"thread_id": thread_id}}
        )  # type: ignore[arg-type,return-value]

        # Continue through phases until we reach TASKS
        while result.get("phase") != Phase.TASKS:
            result = await agent.ainvoke(  # type: ignore[arg-type,return-value]
                result,  # type: ignore[arg-type]
                config={"configurable": {"thread_id": thread_id}},  # type: ignore[arg-type]
            )

        # Drain remaining events
        remaining = await bus.drain()
        for event in remaining:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        # Yield all events from queue
        while not queue.empty():
            try:
                yield queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    finally:
        await conn.close()
        _progress_bus_ctx.set(None)


def pump_and_drain(
    bus: ProgressBus,
    timeout: float = 0.1,
) -> list[ProgressEvent]:
    """Pump and drain all currently available events from the bus.

    Implements the "drain" part of pump-and-drain: collects all
    currently available events.

    Args:
        bus: The progress bus to drain
        timeout: Max time to wait for each event

    Returns:
        List of all events that were drained
    """
    events: list[ProgressEvent] = []

    # Drain all currently available events
    while True:
        try:
            event = bus._queue.get_nowait()  # type: ignore[attr-defined]
            events.append(event)
        except asyncio.QueueEmpty:
            break

    return events
