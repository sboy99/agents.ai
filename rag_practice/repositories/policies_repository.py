from chromadb.api.models.CollectionCommon import Metadata, OneOrMany
from lib.chroma import ChromaDB
from lib.config import Config
from lib.logger import Logger


class PoliciesRepository:
    def __init__(self, cfg: Config):
        self._logger = Logger(__name__)
        self._vector_db = ChromaDB(cfg)
        self._collection_name = cfg.COLLECTION_NAME
        self._default_top_k = cfg.TOP_K
        _has_collection = self._vector_db.collection_exists(self._collection_name)
        if _has_collection:
            self._collection = self._vector_db.get_collection(self._collection_name)
        else:
            self._collection = self._vector_db.create_collection(self._collection_name)

    def add_policy(
        self, id: str, policy_text: str, metadata: OneOrMany[Metadata] | None = None
    ) -> None:
        """Add a policy document to the vector database."""
        self._collection.add(ids=[id], documents=[policy_text], metadatas=metadata)
        self._logger.info("Policy added to vector database")

    def search_policies(self, query: str, k: int | None = None) -> list | None:
        """Search for relevant policies based on a query."""
        if k is None:
            k = self._default_top_k
        results = self._collection.query(
            query_texts=[query], n_results=k, include=["documents"]
        )
        if not results or not results.get("documents"):
            return None
        return results["documents"][0] if results["documents"] else None
