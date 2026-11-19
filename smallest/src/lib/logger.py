"""Global logging configuration for the smallest project.

Usage::

    from lib.logger import logger

    logger.info("hello", user="alice")
    logger.error("failed", code=42)

The module exposes a single ``logger`` instance backed by the standard
library ``logging`` package. Configuration is idempotent: calling
``setup_logging`` more than once is safe and only re-applies the handlers
that are missing, so library code can call it defensively without clobbering
an application-level configuration.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

__all__ = [
    "get_logger",
    "logger",
    "setup_logging",
]

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


class _ContextFormatter(logging.Formatter):
    """Formatter that injects extra fields as ``key=value`` pairs."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _STANDARD_FIELDS and not k.startswith("_")
        }
        if not extras:
            return base
        tail = " ".join(f"{k}={v!r}" for k, v in extras.items())
        return f"{base} | {tail}"


_STANDARD_FIELDS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    }
)


def setup_logging(
    level: int | str = logging.INFO,
    *,
    stream: Any = sys.stderr,
    fmt: str = _DEFAULT_FORMAT,
    datefmt: str = _DEFAULT_DATEFMT,
    force: bool = False,
) -> logging.Logger:
    """Configure the shared ``smallest`` logger.

    Parameters
    ----------
    level:
        Logging level (name or numeric). Defaults to ``INFO``.
    stream:
        Where to write log records. Defaults to ``sys.stderr``.
    fmt / datefmt:
        Format strings forwarded to :class:`logging.Formatter`.
    force:
        When ``True``, remove existing handlers first. Useful when an
        application wants to take over configuration from a library.
    """
    if isinstance(level, str):
        level = logging.getLevelName(level.upper())

    root = logging.getLogger("smallest")
    root.setLevel(level)

    if force:
        for handler in list(root.handlers):
            root.removeHandler(handler)

    formatter = _ContextFormatter(fmt, datefmt=datefmt)

    has_stream = any(getattr(h, "stream", None) is stream for h in root.handlers)
    if not has_stream:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    # Avoid double-logging through the root logger when this package is
    # imported as a library.
    root.propagate = False
    return root


def get_logger(name: str | None = None) -> _LoggerProxy:
    """Return a child logger under the shared ``smallest`` namespace."""
    if name is None or name == "smallest":
        return logger
    return logger.getChild(name)


class _LoggerProxy:
    """Logger wrapper that lets callers pass context as keyword arguments.

    Standard ``logging`` only accepts context via the ``extra=`` argument,
    which is verbose. This proxy merges keyword arguments into ``extra`` so
    code can write ``logger.info("done", user="alice")`` instead of
    ``logger.info("done", extra={"user": "alice"})``.
    """

    __slots__ = ("_logger",)

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        # Standard LogRecord fields must not appear in ``extra``; pull them
        # out and pass them as explicit keyword arguments instead.
        standard: dict[str, Any] = {}
        for key in ("exc_info", "stack_info", "extra"):
            if key in kwargs:
                standard[key] = kwargs.pop(key)
        extra = standard.pop("extra", None) or {}
        if kwargs:
            extra = {**extra, **kwargs}
        self._logger.log(level, msg, *args, extra=extra or None, **standard)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, *args, **kwargs)

    def warn(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("exc_info", True)
        self._log(logging.ERROR, msg, *args, **kwargs)

    def setLevel(self, level: int | str) -> None:
        self._logger.setLevel(level)

    def getChild(self, name: str) -> _LoggerProxy:
        return _LoggerProxy(self._logger.getChild(name))

    @property
    def name(self) -> str:
        return self._logger.name


# Configure once on import so that any ``logger.*`` call works out of the
# box, while still allowing ``setup_logging(force=True)`` to override.
setup_logging()

# Public ``logger`` is a proxy so callers can pass context as kwargs.
logger = _LoggerProxy(logging.getLogger("smallest"))
