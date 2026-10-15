from typing import cast

from chromadb import PersistentClient as ChromaClient
from chromadb.api.types import Embeddable, EmbeddingFunction
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from lib.config import Config


class ChromaDB:
    def __init__(self, cfg: Config):
        self.client = ChromaClient(path=cfg.CHROMA_PATH)
        self.cfg = cfg

    def get_collection(self, name: str):
        return self.client.get_collection(name)

    def create_collection(self, name: str):
        return self.client.create_collection(
            name=name,
            # OpenAIEmbeddingFunction only embeds Documents; chromadb's stub expects Embeddable
            embedding_function=cast(
                EmbeddingFunction[Embeddable],
                OpenAIEmbeddingFunction(
                    api_base=self.cfg.OPENROUTER_BASE_URL,
                    api_key=self.cfg.get_openrouter_api_key(),
                    model_name=self.cfg.EMBEDDING_MODEL,
                ),
            ),
        )

    def list_collections(self):
        return self.client.list_collections()

    def collection_exists(self, name: str) -> bool:
        return any(c.name == name for c in self.client.list_collections())
