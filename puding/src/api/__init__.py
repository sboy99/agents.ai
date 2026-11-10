import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..mcp.client import mcp
from ..services.task_store import task_store
from . import auth, ideas, tasks

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# Silence chatty third-party loggers so our DEBUG traces stay readable.
for _noisy in (
    "httpx",
    "urllib3",
    "openai",
    "langchain",
    "langchain_core",
    "langgraph",
    "asyncio",
    "aiosqlite",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp.start()  # MCP servers (Notion/Linear/Tavily)
    await task_store.start()  # async task DB
    yield
    await mcp.aclose()
    await task_store.aclose()


app = FastAPI(title="Pudding", lifespan=lifespan)


@app.get("/health")
async def health():
    """Liveness check for the Pudding API."""
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(ideas.router)
app.include_router(tasks.router)
