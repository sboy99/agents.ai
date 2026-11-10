from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
CFG_DIR = BASE_DIR / ".puding"

# project root
PROMPTS_DIR = BASE_DIR / "prompts"
SKILLS_DIR = BASE_DIR / "skills"
DB_DIR = CFG_DIR / "db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # ---- LLM (OpenAI-compatible) ----
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.2
    llm_timeout: int = 60
    # Reasoning models count chain-of-thought against this cap, so keep it
    # generous enough for both thinking and the full structured output.
    llm_max_tokens: int = 8000
    llm_required: bool = True

    # ---- OAuth ----
    oauth_redirect_uri: str = ""

    # ---- Notion ----
    notion_parent_db_id: str = ""

    # ---- Tavily search ----
    tavily_api_key: SecretStr = SecretStr("")
    tavily_keyless: bool = False

    # ---- Server ----
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    @field_validator("llm_api_key")
    @classmethod
    def _require_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError("LLM_API_KEY is required")
        return v

    @field_validator("llm_model")
    @classmethod
    def _require_model(cls, v: str) -> str:
        if not v:
            raise ValueError("LLM_MODEL is required")
        return v

    @field_validator("llm_base_url")
    @classmethod
    def _validate_base_url(cls, v: str) -> str:
        if not v:
            raise ValueError("LLM_BASE_URL is required")
        return v

    @field_validator("oauth_redirect_uri")
    @classmethod
    def _require_redirect_uri(cls, v: str) -> str:
        if not v:
            raise ValueError("OAUTH_REDIRECT_URI is required")
        return v

    @field_validator("notion_parent_db_id")
    @classmethod
    def _validate_notion_parent_db_id(cls, v: str) -> str:
        return v  # Optional for page creation


settings = Settings()
