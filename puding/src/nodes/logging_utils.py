"""Logging utilities for pipeline nodes to emit streaming logs."""

import logging

from langgraph.config import get_config

from ..services.task_store import task_store

logger = logging.getLogger(__name__)


def emit_log(level: str, message: str) -> None:
    """Emit a log entry to the task store for SSE streaming.

    Args:
        level: Log level (INFO, DEBUG, WARNING, ERROR)
        message: The log message
    """
    try:
        config = get_config()
        if config and "configurable" in config:
            thread_id = config["configurable"].get("thread_id")
            if thread_id:
                task_store.emit_log(thread_id, level, message)
    except Exception as e:  # noqa: BLE001
        logger.debug("LOGGING_UTILS: Failed to emit log: %s", e)


def log_phase(phase_name: str, details: str = "") -> None:
    """Log a phase transition."""
    emit_log("INFO", f"🚀 {phase_name}: {details}" if details else f"🚀 {phase_name}")


def log_thinking(model: str = "LLM") -> None:
    """Log that LLM is thinking."""
    emit_log("INFO", f"🤔 {model} is thinking...")


def log_done_thinking() -> None:
    """Log that LLM finished thinking."""
    emit_log("INFO", "✅ done thinking")


def log_mcp_tool_call(tool_name: str, args: dict | None = None) -> None:
    """Log an MCP tool call."""
    if args:
        emit_log("INFO", f"<mcp> calling {tool_name} with args: {args}")
    else:
        emit_log("INFO", f"<mcp> calling {tool_name}")


def log_mcp_tool_result(tool_name: str, result_summary: str = "") -> None:
    """Log an MCP tool result."""
    if result_summary:
        emit_log("INFO", f"<mcp> {tool_name} completed: {result_summary}")
    else:
        emit_log("INFO", f"<mcp> {tool_name} completed")
