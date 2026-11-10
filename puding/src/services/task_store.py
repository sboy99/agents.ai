import asyncio
import json
import logging
import time
import uuid
from collections import deque
from collections.abc import AsyncGenerator

import aiosqlite

from ..config import DB_DIR

logger = logging.getLogger(__name__)

TASKS_DB = DB_DIR / "tasks.db"


class LogEntry:
    """Represents a single log entry for SSE streaming."""

    def __init__(self, level: str, message: str, timestamp: float | None = None):
        self.level = level
        self.message = message
        self.timestamp = timestamp or time.time()

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        return f"event: log\nid: {int(self.timestamp * 1000)}\ndata: {json.dumps(self.__dict__)}\n\n"


class TaskStore:
    def __init__(self, path=TASKS_DB):
        self.path = str(path)
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        # In-memory circular buffer for recent logs per thread (for SSE streaming)
        self._log_buffers: dict[str, deque] = {}
        self._log_subscribers: dict[str, asyncio.Queue] = {}

    async def start(self) -> None:
        logger.debug("TaskStore: Acquiring lock for DB connection")
        async with self._lock:
            if self._db is not None:
                logger.debug("TaskStore: DB already connected, skipping initialization")
                return
            logger.debug("TaskStore: Connecting to SQLite DB at %s", self.path)
            self._db = await aiosqlite.connect(self.path)
            self._db.row_factory = aiosqlite.Row
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    identifier TEXT NOT NULL,
                    title TEXT NOT NULL,
                    prd TEXT,
                    acceptance TEXT,
                    priority TEXT,
                    area TEXT,
                    out_of_scope TEXT,
                    spec_excerpt TEXT,
                    status TEXT DEFAULT 'todo',
                    created_at REAL,
                    updated_at REAL,
                    UNIQUE(thread_id, identifier)
                )""")
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_thread ON tasks(thread_id)"
            )
            await self._db.commit()
            logger.debug("TaskStore: DB initialized successfully")

    def _ensure_thread_buffers(self, thread_id: str):
        """Ensure log buffer and subscriber exist for a thread."""
        if thread_id not in self._log_buffers:
            self._log_buffers[thread_id] = deque(maxlen=1000)  # Keep last 1000 logs
        if thread_id not in self._log_subscribers:
            self._log_subscribers[thread_id] = asyncio.Queue()

    async def create_many(self, thread_id: str, tickets: list[dict]) -> None:
        logger.debug(
            "TaskStore: Creating %d tickets for thread_id=%s", len(tickets), thread_id
        )
        await self.start()
        conn = self._db
        assert conn is not None  # type: ignore[unreachable]

        now = time.time()
        rows = []
        for t in tickets:
            rows.append(
                (
                    str(uuid.uuid4()),
                    thread_id,
                    t["identifier"],
                    t["title"],
                    t.get("prd", ""),
                    json.dumps(t.get("acceptance") or []),
                    t.get("priority", "medium"),
                    t.get("area", "core"),
                    t.get("out_of_scope", ""),
                    t.get("spec_excerpt", ""),
                    t.get("status", "todo"),
                    now,
                    now,
                )
            )
        if rows:
            await conn.executemany(
                """
                INSERT OR REPLACE INTO tasks
                (id, thread_id, identifier, title, prd, acceptance, priority,
                 area, out_of_scope, spec_excerpt, status, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
                rows,
            )
            await conn.commit()
            logger.debug("TaskStore: Persisted %d rows", len(rows))

    async def list_by_thread(self, thread_id: str) -> list[dict]:
        logger.debug("TaskStore: Listing tasks for thread_id=%s", thread_id)
        await self.start()
        conn = self._db
        assert conn is not None  # type: ignore[unreachable]

        cur = await conn.execute(
            "SELECT * FROM tasks WHERE thread_id=? ORDER BY created_at", (thread_id,)
        )
        rows = [self._row_to_dict(r) for r in await cur.fetchall()]
        logger.debug("TaskStore: Found %d tasks", len(rows))
        return rows

    async def get(self, thread_id: str, identifier: str) -> dict | None:
        logger.debug(
            "TaskStore: Getting task %s for thread_id=%s", identifier, thread_id
        )
        await self.start()
        conn = self._db
        assert conn is not None  # type: ignore[unreachable]

        cur = await conn.execute(
            "SELECT * FROM tasks WHERE thread_id=? AND identifier=?",
            (thread_id, identifier),
        )
        row = await cur.fetchone()
        result = self._row_to_dict(row) if row else None
        logger.debug(
            "TaskStore: Task %s %s", identifier, "found" if result else "not found"
        )
        return result

    async def current_for_thread(self, thread_id: str) -> dict | None:
        """First not-done task, by creation order."""
        logger.debug(
            "TaskStore: Getting current (not-done) task for thread_id=%s", thread_id
        )
        await self.start()
        conn = self._db
        assert conn is not None  # type: ignore[unreachable]

        cur = await conn.execute(
            """
            SELECT * FROM tasks WHERE thread_id=? AND status != 'done'
            ORDER BY created_at LIMIT 1""",
            (thread_id,),
        )
        row = await cur.fetchone()
        result = self._row_to_dict(row) if row else None
        logger.debug(
            "TaskStore: Current task %s", result["identifier"] if result else "none"
        )
        return result

    async def update_status(
        self, thread_id: str, identifier: str, status: str
    ) -> dict | None:
        logger.debug("TaskStore: Updating task %s to status=%s", identifier, status)
        await self.start()
        conn = self._db
        assert conn is not None  # type: ignore[unreachable]

        await conn.execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE thread_id=? AND identifier=?",
            (status, time.time(), thread_id, identifier),
        )
        await conn.commit()
        result = await self.get(thread_id, identifier)
        logger.debug("TaskStore: Status updated successfully")
        return result

    async def aclose(self) -> None:
        logger.debug("TaskStore: Closing DB connection")
        async with self._lock:
            if self._db is not None:
                await self._db.close()
                self._db = None
            # Clear all buffers and subscribers
            self._log_buffers.clear()
            for queue in self._log_subscribers.values():
                while not queue.empty():
                    queue.get_nowait()

    def emit_log(self, thread_id: str, level: str, message: str) -> None:
        """Emit a log entry for a thread (for SSE streaming).

        Args:
            thread_id: The thread ID to emit the log for
            level: Log level (INFO, DEBUG, WARNING, ERROR)
            message: The log message
        """
        entry = LogEntry(level, message)
        self._ensure_thread_buffers(thread_id)

        # Add to circular buffer
        self._log_buffers[thread_id].append(entry)

        # Notify subscribers via queue
        if thread_id in self._log_subscribers:
            self._log_subscribers[thread_id].put_nowait(entry)

    async def stream_logs(self, thread_id: str) -> AsyncGenerator[str, None]:
        """Stream logs for a thread as Server-Sent Events.

        First yields all buffered logs, then waits for new logs.

        Args:
            thread_id: The thread ID to stream logs for

        Yields:
            SSE-formatted log entries
        """
        self._ensure_thread_buffers(thread_id)

        # First, yield all buffered logs
        for entry in self._log_buffers[thread_id]:
            yield entry.to_sse()

        # Then, wait for new logs
        queue = self._log_subscribers[thread_id]
        while True:
            try:
                entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield entry.to_sse()
            except TimeoutError:
                # Keep the connection alive with a comment
                yield ": keep-alive\n\n"

    async def get_logs(self, thread_id: str, limit: int = 100) -> list[dict]:
        """Get recent logs for a thread (for polling fallback).

        Args:
            thread_id: The thread ID to get logs for
            limit: Maximum number of logs to return

        Returns:
            List of log entry dicts
        """
        self._ensure_thread_buffers(thread_id)
        buffer = self._log_buffers.get(thread_id, deque())
        return [
            {"timestamp": e.timestamp, "level": e.level, "message": e.message}
            for e in list(buffer)[-limit:]
        ]

    @staticmethod
    def _row_to_dict(r: aiosqlite.Row) -> dict:
        return {
            "id": r["id"],
            "identifier": r["identifier"],
            "thread_id": r["thread_id"],
            "title": r["title"],
            "prd": r["prd"],
            "acceptance": json.loads(r["acceptance"] or "[]"),
            "priority": r["priority"],
            "area": r["area"],
            "out_of_scope": r["out_of_scope"],
            "spec_excerpt": r["spec_excerpt"],
            "status": r["status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }


task_store = TaskStore()
