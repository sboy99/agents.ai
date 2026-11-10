"""Dev server runner for pudding.

Usage:
    uv run dev-server  # with [dev] optional dependencies

Note: uvicorn should be installed. Use:
    uv sync --extra dev
    # or
    uv pip install uvicorn[standard]
"""

import os

import uvicorn

from ..config import settings


def main():
    uvicorn.run(
        "src.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        reload_dirs=[os.path.dirname(os.path.dirname(os.path.abspath(__file__)))],
    )


if __name__ == "__main__":
    main()
