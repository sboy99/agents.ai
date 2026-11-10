import os
from typing import cast

from dotenv import load_dotenv


class Config:
    GEMINI_API_KEY: str
    GEMINI_MODEL: str
    OPENAI_API_KEY: str
    OPENAI_MODEL: str
    OPENAI_BASE_URL: str

    def __init__(self):
        load_dotenv()
        self.GEMINI_API_KEY = self._get_or_throw("GEMINI_API_KEY")
        self.GEMINI_MODEL = self._get_or_throw("GEMINI_MODEL")

        self.OPENAI_API_KEY = self._get_or_throw("OPENAI_API_KEY")
        self.OPENAI_MODEL = self._get_or_throw("OPENAI_MODEL")
        self.OPENAI_BASE_URL = self._get_or_throw("OPENAI_BASE_URL")

    def _get_or_throw[T = str](self, key: str) -> T:
        value = os.environ.get(key)
        if not value:
            raise ValueError(f"Environment variable {key} is not set")
        return cast(T, value)
