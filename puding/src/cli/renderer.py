"""Rich terminal renderer for progress events.

Provides visual feedback including phase status spinners,
phase transition visuals, and event display.
"""

import asyncio
import sys
from dataclasses import dataclass, field

from ..services.progress import ProgressEvent, Status


@dataclass
class RenderState:
    """Tracks current rendering state."""

    current_phase: str = ""
    current_message: str = ""
    status: str = ""
    transition_animating: bool = False
    spinner_index: int = field(default=0, init=False)
    spinner_frames: list[str] = field(
        default_factory=lambda: ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    )


class TerminalRenderer:
    """Renders progress events to the terminal with rich formatting.

    Provides:
    - Phase status spinners during processing
    - Phase transition visuals
    - Color-coded event display
    - Timestamped messages
    """

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.state = RenderState()
        self._hidden_cursor = False

    def _save_cursor(self):
        """Save cursor position for redrawing."""
        self.stream.write("\033[s")

    def _restore_cursor(self):
        """Restore cursor position."""
        self.stream.write("\033[u")

    def _hide_cursor(self):
        """Hide the terminal cursor."""
        self.stream.write("\033[?25l")
        self._hidden_cursor = True

    def _show_cursor(self):
        """Show the terminal cursor."""
        if self._hidden_cursor:
            self.stream.write("\033[?25h")
            self._hidden_cursor = False

    def _clear_line(self):
        """Clear the current line."""
        self.stream.write("\r\033[K")

    def _move_cursor_up(self, lines: int = 1):
        """Move cursor up by specified lines."""
        self.stream.write(f"\033[{lines}A")

    def _move_cursor_down(self, lines: int = 1):
        """Move cursor down by specified lines."""
        self.stream.write(f"\033[{lines}B")

    def _color(self, text: str, color_code: int) -> str:
        """Apply ANSI color to text."""
        return f"\033[{color_code}m{text}\033[0m"

    def _spinner_char(self) -> str:
        """Get current spinner frame character."""
        char = self.state.spinner_frames[self.state.spinner_index]
        self.state.spinner_index = (self.state.spinner_index + 1) % len(
            self.state.spinner_frames
        )
        return char

    def render_event(self, event: ProgressEvent):
        """Render a single progress event.

        Args:
            event: The progress event to render
        """
        # Clear any active status line
        self._clear_line()

        # Color based on status
        if event.status == Status.START:
            status_color = 36  # Cyan
            prefix = "▶"
        elif event.status == Status.COMPLETE:
            status_color = 32  # Green
            prefix = "✓"
        elif event.status == Status.ERROR:
            status_color = 31  # Red
            prefix = "✗"
        else:  # Progress
            status_color = 33  # Yellow
            prefix = "●"

        # Format the phase name
        phase_display = self._color(event.phase.upper(), 35)  # Magenta
        timestamp = self._color(f"[{event.human_time}]", 90)  # Dark gray

        # Build the output line
        line = f"{timestamp} {self._color(prefix, status_color)} {phase_display}: {event.message}"

        # Add spinner for ongoing phases
        if event.status == Status.START:
            spinner = self._spinner_char()
            line = f"\n {spinner} {line}"

        self.stream.write(line)
        self.stream.flush()

        # Update internal state
        if event.status in (Status.START, Status.PROGRESS):
            self.state.current_phase = event.phase
            self.state.current_message = event.message
            self.state.status = event.status

    def render_transition(self, from_phase: str, to_phase: str):
        """Render a phase transition visual.

        Args:
            from_phase: The phase we're leaving
            to_phase: The phase we're entering
        """
        self._clear_line()

        # Simple transition text (no animation in sync context)
        arrow = self._color("→", 33)
        self.stream.write(
            f"\n {arrow} {self._color(from_phase, 35)} → {self._color(to_phase, 32)}\n"
        )
        self.stream.flush()

        # Update state
        self.state.current_phase = to_phase

    async def render_transition_async(self, from_phase: str, to_phase: str):
        """Render a phase transition visual with animation.

        Async version with fade animation.

        Args:
            from_phase: The phase we're leaving
            to_phase: The phase we're entering
        """
        self._clear_line()

        # Fade out from phase
        fade_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        for char in fade_chars:
            self.stream.write(f"\r {self._color(char, 35)} {from_phase} → {to_phase} ")
            self.stream.flush()
            await asyncio.sleep(0.05)

        # Final transition
        self._clear_line()
        arrow = self._color("→", 33)
        self.stream.write(
            f"\n {arrow} {self._color(from_phase, 35)} → {self._color(to_phase, 32)}\n"
        )
        self.stream.flush()

        # Update state
        self.state.current_phase = to_phase

    def render_spinner(self, phase: str, message: str):
        """Render an animated spinner for a phase.

        Args:
            phase: Current phase name
            message: Status message
        """
        spinner = self._spinner_char()
        self._save_cursor()
        self._clear_line()
        self.stream.write(f" {spinner} {self._color(phase, 35)}: {message} ")
        self.stream.flush()

    def finish(self):
        """Call when rendering is complete to clean up."""
        self._show_cursor()
        self._clear_line()


async def render_events(event_stream: asyncio.Queue[ProgressEvent]):
    """Async generator that renders events and yields them.

    This function takes ownership of rendering while also passing through
    events to downstream consumers.

    Args:
        event_stream: Queue receiving progress events

    Yields:
        ProgressEvent objects (passed through)
    """
    renderer = TerminalRenderer()
    renderer._hide_cursor()

    try:
        while True:
            try:
                event = await asyncio.wait_for(event_stream.get(), timeout=0.1)
                renderer.render_event(event)
                yield event
            except TimeoutError:
                # Check if stream is done periodically
                continue
    finally:
        renderer.finish()


def format_event_line(event: ProgressEvent) -> str:
    """Format a single event as a one-line string for logging.

    Args:
        event: The progress event to format

    Returns:
        Formatted string representation
    """
    prefix_map = {
        Status.START: "▶",
        Status.PROGRESS: "●",
        Status.COMPLETE: "✓",
        Status.ERROR: "✗",
    }

    prefix = prefix_map.get(event.status, "?")
    timestamp = event.human_time

    return f"[{timestamp}] {prefix} {event.phase}: {event.message}"
