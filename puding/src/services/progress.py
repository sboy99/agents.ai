"""Progress event system for streaming pipeline execution to CLI.

Provides ProgressEvent schema and ProgressBus with ContextVar-based
context management for thread-safe event broadcasting.
"""

import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Status(str, Enum):
    """Progress event status types."""

    START = "start"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ProgressEvent:
    """Schema for a progress event emitted during pipeline execution.

    Attributes:
        phase: The current pipeline phase (e.g., 'research', 'analyze', 'write_spec')
        status: The status of the operation (start/progress/complete/error)
        message: Human-readable description of the progress
        timestamp: When the event was created (defaults to now)
        step: Optional sub-step identifier (e.g., 'search_query_1')
        data: Optional arbitrary payload for rich event data
    """

    phase: str
    status: Status
    message: str
    timestamp: float = field(default_factory=lambda: time.time())
    step: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "phase": self.phase,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "step": self.step,
            "data": self.data,
        }

    @property
    def human_time(self) -> str:
        """Return a human-readable timestamp."""
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")


# ContextVar for storing the progress bus in the current execution context
_progress_bus_ctx: ContextVar["ProgressBus | None"] = ContextVar(
    "progress_bus_ctx", default=None
)


class ProgressBus:
    """Thread-safe broadcast bus for progress events.

    Uses ContextVar to store/receive the bus, allowing any code that has
    a reference to the bus to emit events without explicit passing.

    Usage:
        bus = ProgressBus()
        bus.set_current()  # Store in context
        bus.emit(event)    # Broadcast event
    """

    def __init__(self):
        self._queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
        # Store the token for this bus instance - used to restore context
        self._token = None  # type: ignore[assignment]

    def _set_current_internal(self) -> None:
        """Internal: Set this bus as the current bus in context."""
        self._token = _progress_bus_ctx.set(self)

    @classmethod
    def current(cls) -> "ProgressBus | None":
        """Get the current bus from context, or None if not set."""
        return _progress_bus_ctx.get()

    @classmethod
    def set_current(cls) -> "ProgressBus":
        """Create and set a new bus as the current context's bus."""
        bus = cls()
        bus._set_current_internal()
        return bus

    def emit(self, event: ProgressEvent) -> None:
        """Queue an event for broadcast to listeners."""
        # Use put_nowait to avoid blocking; drop if queue is full
        # (unlikely in normal operation since consumers drain actively)
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            pass  # Silently drop if no listeners

    async def listen(self) -> asyncio.Queue[ProgressEvent]:
        """Return a queue that receives all emitted events.

        Returns the same queue - consumers call get() to receive events.
        """
        return self._queue

    async def drain(self, timeout: float | None = None) -> list[ProgressEvent]:
        """Drain all currently queued events.

        Returns immediately with whatever is available.
        """
        events: list[ProgressEvent] = []
        while True:
            try:
                event = self._queue.get_nowait()
                events.append(event)
            except asyncio.QueueEmpty:
                break
        return events


async def emit_phase_start(phase: str, message: str) -> None:
    """Convenience function to emit a phase start event."""
    bus = ProgressBus.current()
    if bus:
        bus.emit(
            ProgressEvent(
                phase=phase,
                status=Status.START,
                message=message,
            )
        )


async def emit_phase_complete(phase: str, message: str) -> None:
    """Convenience function to emit a phase complete event."""
    bus = ProgressBus.current()
    if bus:
        bus.emit(
            ProgressEvent(
                phase=phase,
                status=Status.COMPLETE,
                message=message,
            )
        )


async def emit_progress(phase: str, message: str, step: str | None = None) -> None:
    """Convenience function to emit a progress event."""
    bus = ProgressBus.current()
    if bus:
        bus.emit(
            ProgressEvent(
                phase=phase,
                status=Status.PROGRESS,
                message=message,
                step=step,
            )
        )


async def emit_error(phase: str, message: str) -> None:
    """Convenience function to emit an error event."""
    bus = ProgressBus.current()
    if bus:
        bus.emit(
            ProgressEvent(
                phase=phase,
                status=Status.ERROR,
                message=message,
            )
        )
