import logging

from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI

from ..config import settings

logger = logging.getLogger(__name__)


class StreamLoggingHandler(BaseCallbackHandler):
    """Callback handler for logging LLM thinking progress."""

    def on_llm_start(
        self,
        serialized: dict,
        prompts: list,
        **kwargs,
    ):
        """Log when LLM starts thinking."""
        model_name = serialized.get("name", "unknown")
        logger.info("🤔 thinking... (model: %s)", model_name)

    def on_llm_end(self, response, **kwargs):
        """Log when LLM finishes thinking."""
        logger.info("✅ done thinking")


def get_llm(callbacks: list | None = None):
    """Get the LLM instance with optional callbacks for streaming logs.

    Args:
        callbacks: Optional list of LangChain callback handlers.
                   If not provided, StreamLoggingHandler will be added by default.

    Returns:
        ChatOpenAI: Configured LLM instance
    """
    if callbacks is None:
        callbacks = [StreamLoggingHandler()]

    logger.debug(
        "LLM: Creating ChatOpenAI instance model=%s base_url=%s max_tokens=%s",
        settings.llm_model,
        settings.llm_base_url,
        settings.llm_max_tokens,
    )
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout,
        max_completion_tokens=settings.llm_max_tokens,
        callbacks=callbacks,
    )
