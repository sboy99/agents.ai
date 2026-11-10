import logging

logger = logging.getLogger(__name__)

from ..config import PROMPTS_DIR

_cache = {}


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if path in _cache:
        logger.debug("PROMPT: Cache hit for '%s'", name)
        return _cache[path]
    logger.debug("PROMPT: Loading prompt '%s' from %s", name, path)
    _cache[path] = path.read_text(encoding="utf-8")
    return _cache[path]
