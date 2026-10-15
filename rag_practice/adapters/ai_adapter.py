from decorators import catch_exceptions
from lib import Logger
from lib.config import Config
from openai import OpenAI


class AIAdapter:
    def __init__(self, cfg: Config) -> None:
        self._logger = Logger(__name__)
        self._cfg = cfg

    @catch_exceptions()
    def chat(self, prompt: str) -> str | None:
        completion = self._get_xkiro_proxy().chat.completions.create(
            model=self._cfg.AI_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        return completion.choices[0].message.content

    @catch_exceptions()
    def get_embeddings(self, text: str) -> list[float]:
        embeddings_client = self._get_openrouter_proxy()
        response = embeddings_client.embeddings.create(
            input=text, model=self._cfg.EMBEDDING_MODEL
        )
        return response.data[0].embedding

    def _get_xkiro_proxy(self) -> OpenAI:
        return OpenAI(
            base_url=self._cfg.XKIRO_BASE_URL,
            api_key=self._cfg.get_xkiro_api_key(),
        )

    def _get_openrouter_proxy(self) -> OpenAI:
        return OpenAI(
            base_url=self._cfg.OPENROUTER_BASE_URL,
            api_key=self._cfg.get_openrouter_api_key(),
        )
