"""Traced decorator for LangGraph node functions.

Provides a decorator that wraps node functions to emit progress events
before and after execution, and on any errors.
"""

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any

from ..services.progress import (
    ProgressBus,
    ProgressEvent,
    emit_error,
    emit_phase_complete,
    emit_phase_start,
)

logger = logging.getLogger(__name__)


def traced(phase: str, description: str | None = None):
    """Decorator for LangGraph node functions to emit progress events.

    Wraps a sync or async node function to:
    1. Emit a START event before execution (with optional bus setup)
    2. Execute the function
    3. Emit a COMPLETE event on success
    4. Emit an ERROR event on exception

    Args:
        phase: The phase name for progress events (e.g., 'research', 'analyze')
        description: Optional description shown in progress events

    Returns:
        Decorated function that emits progress events
    """

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Check if there's already a progress bus in context
            # If not, we'll create one (for standalone execution)
            bus = ProgressBus.current()
            bus_was_none = bus is None
            if bus_was_none:
                bus = ProgressBus.set_current()

            # Emit start event
            msg = description or f"Starting {phase} phase"
            await emit_phase_start(phase, msg)
            logger.debug("TRACED: Emitted START for phase=%s", phase)

            try:
                result = await func(*args, **kwargs)
                await emit_phase_complete(phase, f"Completed {phase} phase")
                logger.debug("TRACED: Emitted COMPLETE for phase=%s", phase)
                return result
            except Exception as e:
                await emit_error(phase, f"{phase} failed: {e}")
                logger.warning("TRACED: Emitted ERROR for phase=%s: %s", phase, e)
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, run async wrapper in event loop
            return asyncio.run(async_wrapper(*args, **kwargs))

        return async_wrapper if is_async else sync_wrapper

    return decorator


def _extract_state_info(state: Any) -> dict:
    """Extract useful info from a state object for progress events."""
    if not isinstance(state, dict):
        return {}

    info = {}
    # Common state fields that help identify what we're processing
    if "idea" in state:
        idea = state["idea"]
        if isinstance(idea, str) and len(idea) > 50:
            info["idea"] = idea[:50] + "..."
        else:
            info["idea"] = idea
    if "phase" in state:
        info["phase"] = str(state["phase"])
    if "research" in state and isinstance(state["research"], dict):
        info["has_research"] = True
    if "tickets" in state and isinstance(state["tickets"], list):
        info["ticket_count"] = len(state["tickets"])

    return info


def emit_event(event: ProgressEvent) -> Callable:
    """Factory for creating emit functions with a specific event type.

    Usage:
        emit_start('research').phase_start()
    """
    return _EventEmitter(event)


class _EventEmitter:
    """Helper class for fluent event emission."""

    def __init__(self, event: ProgressEvent):
        self._event = event

    def phase_start(self) -> None:
        """Emit this event immediately."""
        bus = ProgressBus.current()
        if bus:
            bus.emit(self._event)

    def __call__(self) -> None:
        self.phase_start()
