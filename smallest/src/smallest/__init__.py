"""smallest — smallest entry point."""

from lib.logger import logger


def main() -> None:
    logger.info("smallest starting up", version="0.1.0")
    print("Hello from smallest!")


__all__ = ["main"]