import logging

from langchain_openai import ChatOpenAI

from ..config import settings

logger = logging.getLogger(__name__)


def get_llm():
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
    )
