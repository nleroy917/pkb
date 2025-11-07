from abc import ABC, abstractmethod
from typing import List, Optional

from pkb.core.models import Document


class BaseSearchBackend(ABC):
    """
    Base class for all search backends.

    Backends are responsible for:
    1. Creating indexes/collections
    2. Loading documents with embeddings
    3. Performing searches
    4. Managing backend-specific operations
    """

    def __init__(self, name: str):
        """
        Initialize backend.

        Args:
            name: Backend name (e.g., 'elasticsearch_keyword', 'qdrant')
        """
        self.name = name

    @abstractmethod
    def create_index(self) -> None:
        """
        Create the index/collection in the backend.
        Should be idempotent (safe to call multiple times).
        """
        raise NotImplementedError

    @abstractmethod
    def index_document(
        self, document: Document, embeddings: Optional[List[List[float]]] = None
    ) -> None:
        """
        Index a single document.

        Args:
            document: Document to index
            embeddings: Optional embeddings for document chunks (one per chunk)
        """
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        """
        Delete a document by ID.

        Args:
            document_id: Document ID to delete
        """
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, top_k: int = 10, **kwargs) -> List[dict]:
        """
        Search the backend.

        Args:
            query: Search query
            top_k: Number of results to return
            **kwargs: Backend-specific search parameters

        Returns:
            List of search results with scores and metadata
        """
        raise NotImplementedError

    @abstractmethod
    def get_stats(self) -> dict:
        """
        Get backend statistics (document count, etc.).

        Returns:
            Dictionary of statistics
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """
        Clear all documents from the backend.
        """
        raise NotImplementedError

    def needs_embeddings(self) -> bool:
        """
        Check if this backend requires embeddings.

        Returns:
            True if backend needs embeddings (vector/semantic search)
        """
        return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"
