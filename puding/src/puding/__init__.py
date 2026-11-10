"""Pudding core module with CLI integration.

This module provides the entry point for running the pudding pipeline
with optional streaming progress output.
"""

import argparse
import asyncio
import logging
import sys
import uuid

from langgraph.types import Command

from ..graph import build_graph, pending_questions
from ..mcp.client import mcp
from ..services.task_store import task_store
from ..types import Phase


async def _main(verbose: bool = False):
    """Run the main pipeline with optional streaming output.

    Args:
        streaming: If True, show real-time progress events in terminal
        verbose: If True, enable verbose logging including token streams

    Returns:
        Final state of the pipeline
    """
    # Set up logging based on verbosity
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            stream=sys.stderr,
        )
        # Reduce noise from third-party loggers
        for noisy in (
            "httpx",
            "urllib3",
            "openai",
            "langchain",
            "langgraph",
            "asyncio",
            "aiosqlite",
        ):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    tid = uuid.uuid4().hex
    idea = input("Paste your idea: ")

    # Legacy non-streaming mode
    agent, state_conn = await build_graph()

    try:
        result = await agent.ainvoke(
            {"phase": Phase.IDEA, "idea": idea},
            config={"configurable": {"thread_id": tid}},
        )

        while True:
            qs = await pending_questions(result)
            if not qs:
                break
            answers = []
            for i, q in enumerate(qs):
                print("\nQ" + str(i + 1) + ": " + q["question"])
                answers.append({"id": q["id"], "answer": input("Ans: ")})

            result = await agent.ainvoke(
                Command(resume=answers),
                config={"configurable": {"thread_id": tid}},
            )

        state = (
            await agent.aget_state(config={"configurable": {"thread_id": tid}})
        ).values
        print("\nPhase:", state.get("phase"))
        print("Verdict:", state.get("scorecard", {}).get("verdict"))
        print("Tickets:", len(state.get("tickets", [])))
    finally:
        if state_conn:
            await state_conn.close()
        # Clean up database connections before exit
        await task_store.aclose()
        await mcp.aclose()

    return {"result": result, "verbose": verbose}


def main():
    """Entry point for uv run puding"""
    parser = argparse.ArgumentParser(
        description="Pudding: Turn ideas into implementation tickets"
    )
    parser.add_argument(
        "--no-stream", action="store_true", help="Disable streaming progress output"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output including token streams",
    )

    args = parser.parse_args()

    asyncio.run(_main(verbose=args.verbose))


if __name__ == "__main__":
    main()
