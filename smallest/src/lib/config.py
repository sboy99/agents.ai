from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
CFG_DIR = BASE_DIR / ".smalest"

# project root
PROMPTS_DIR = BASE_DIR / "prompts"
SKILLS_DIR = BASE_DIR / "skills"
DB_DIR = CFG_DIR / "db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # ---- LLM (OpenAI-compatible) ----
    smallest_api_key: SecretStr = SecretStr("")

    # ---- Server ----
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    @field_validator("smallest_api_key")
    @classmethod
    def _require_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError("SMALLEST_API_KEY is required")
        return v


settings = Settings()
