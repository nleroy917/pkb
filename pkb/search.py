from typing import List, Optional

from pkb.embeddings import EmbeddingGenerator
from pkb.search_backends.base import BaseSearchBackend


class SearchResult:
    """
    Unified search result format.
    """

    def __init__(
        self,
        id: str,
        score: float,
        source: str,
        file_path: str,
        content: str,
        metadata: dict,
        backend: str,
        chunk_id: Optional[int] = None,
    ):
        self.id = id
        self.score = score
        self.source = source
        self.file_path = file_path
        self.content = content
        self.metadata = metadata
        self.backend = backend
        self.chunk_id = chunk_id

    def __repr__(self) -> str:
        return f"SearchResult(id={self.id}, score={self.score:.4f}, source={self.source}, backend={self.backend})"


class SearchEngine:
    """
    Unified search interface that can query multiple backends.

    This class provides a consistent API for searching across different
    search backends (keyword, vector, hybrid, etc.). It can be used
    both in the CLI and in the REST API server.
    """

    def __init__(
        self,
        backends: Optional[List[BaseSearchBackend]] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize search engine.

        Args:
            backends: List of search backends to query
            embedding_generator: Optional embedding generator for vector search
        """
        self.backends = backends or []
        self.embedding_generator = embedding_generator

    def add_backend(self, backend: BaseSearchBackend) -> None:
        """
        Add a search backend.

        Args:
            backend: Backend to add
        """
        self.backends.append(backend)

    def search(
        self,
        query: str,
        backend_type: Optional[str] = None,
        top_k: int = 10,
        **kwargs,
    ) -> List[SearchResult]:
        """
        Search across configured backends.

        Args:
            query: Search query
            backend_type: Optional backend type filter (keyword, vector, etc.)
            top_k: Number of results to return per backend
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        if not self.backends:
            raise ValueError("No search backends configured")

        all_results = []

        for backend in self.backends:
            # skip if filtering and this isn't the right backend type
            if backend_type and not self._matches_backend_type(
                backend.name, backend_type
            ):
                continue

            try:
                # prepare query embedding if needed
                query_embedding = None
                if backend.needs_embeddings():
                    if not self.embedding_generator:
                        self.embedding_generator = EmbeddingGenerator()
                    query_embedding = self.embedding_generator.encode(
                        [query], show_progress=False
                    )[0].tolist()

                # perform search
                results = backend.search(
                    query=query,
                    top_k=top_k,
                    query_embedding=query_embedding,
                    **kwargs,
                )

                # convert to unified format
                for result in results:
                    all_results.append(
                        SearchResult(
                            id=result["id"],
                            score=result["score"],
                            source=result["source"],
                            file_path=result["file_path"],
                            content=result["content"],
                            metadata=result.get("metadata", {}),
                            backend=backend.name,
                            chunk_id=result.get("chunk_id"),
                        )
                    )

            except Exception as e:
                print(f"Warning: Search failed for backend {backend.name}: {e}")
                continue

        # sort by score (descending)
        all_results.sort(key=lambda x: x.score, reverse=True)

        # limit to top_k if we searched multiple backends
        if len(self.backends) > 1 and backend_type is None:
            all_results = all_results[:top_k]

        return all_results

    def search_keyword(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        Search using keyword/BM25 backends only.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of search results
        """
        return self.search(query=query, backend_type="keyword", top_k=top_k)

    def search_vector(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        Search using vector/semantic backends only.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of search results
        """
        return self.search(query=query, backend_type="vector", top_k=top_k)

    def _matches_backend_type(self, backend_name: str, backend_type: str) -> bool:
        """
        Check if a backend name matches a backend type filter.

        Args:
            backend_name: Name of the backend
            backend_type: Backend type to match (keyword, vector, etc.)

        Returns:
            True if backend matches type
        """
        backend_name_lower = backend_name.lower()
        backend_type_lower = backend_type.lower()

        return backend_type_lower in backend_name_lower

    def get_backend_stats(self) -> dict:
        """
        Get statistics for all configured backends.

        Returns:
            Dictionary mapping backend names to stats
        """
        stats = {}
        for backend in self.backends:
            try:
                stats[backend.name] = backend.get_stats()
            except Exception as e:
                stats[backend.name] = {"error": str(e)}

        return stats

    def __repr__(self) -> str:
        return f"SearchEngine(backends={len(self.backends)})"
