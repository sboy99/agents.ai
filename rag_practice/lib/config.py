from typing import cast

from dotenv import load_dotenv


class Config:
    COLLECTION_NAME = "policies"
    DATA_PATH = "data"
    CHROMA_PATH = "chroma"
    TOP_K = 4
    AI_MODEL = "qwen/qwen3-max:free"
    EMBEDDING_MODEL = "nvidia/nemotron-3-embed-1b:free"
    XKIRO_BASE_URL = "https://api.xkiro.com/v1"
    _XKIRO_API_KEY: str
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    _OPENROUTER_API_KEY: str

    def __init__(self):
        load_dotenv()
        self._XKIRO_API_KEY = self._get_or_throw("XKIRO_API_KEY")
        self._OPENROUTER_API_KEY = self._get_or_throw("OPENROUTER_API_KEY")

    def get_xkiro_api_key(self) -> str:
        return self._XKIRO_API_KEY

    def get_openrouter_api_key(self) -> str:
        return self._OPENROUTER_API_KEY

    def _get_or_throw[T = str](self, key: str) -> T:
        import os

        value = os.environ.get(key)
        if not value:
            raise ValueError(f"{key} environment variable is not set")
        return cast(T, value)
