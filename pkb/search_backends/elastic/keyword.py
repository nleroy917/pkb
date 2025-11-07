from typing import List, Optional

from elasticsearch import Elasticsearch

from pkb.core.models import Document
from pkb.search_backends.base import BaseSearchBackend


class ElasticsearchKeywordBackend(BaseSearchBackend):
    """
    Elasticsearch backend for keyword/BM25 search.
    """

    def __init__(
        self,
        index_name: str = "pkb_keyword",
        host: str = "localhost",
        port: int = 9200,
    ):
        """
        Initialize Elasticsearch keyword backend.

        Args:
            index_name: Name of the Elasticsearch index
            host: Elasticsearch host
            port: Elasticsearch port
        """
        super().__init__(name=f"elasticsearch_keyword_{index_name}")
        self.index_name = index_name
        self.host = host
        self.port = port
        self.client = Elasticsearch([f"http://{host}:{port}"])

    def create_index(self) -> None:
        """
        Create Elasticsearch index with keyword search mapping.
        """
        if self.client.indices.exists(index=self.index_name):
            print(f"Index {self.index_name} already exists")
            return

        mappings = {
            "properties": {
                "doc_id": {"type": "keyword"},
                "source": {"type": "keyword"},
                "file_path": {"type": "keyword"},
                "content": {
                    "type": "text",
                    "analyzer": "standard",
                },
                "chunks": {
                    "type": "text",
                    "analyzer": "standard",
                },
                "metadata": {
                    "type": "object",
                    "enabled": True,
                },
            }
        }

        self.client.indices.create(
            index=self.index_name,
            mappings=mappings,
        )
        print(f"Created index: {self.index_name}")

    def index_document(
        self, document: Document, embeddings: Optional[List[List[float]]] = None
    ) -> None:
        """
        Index a document for keyword search.

        Args:
            document: Document to index
            embeddings: Ignored for keyword search
        """
        doc_body = {
            "doc_id": document.id,
            "source": document.source,
            "file_path": document.file_path,
            "content": document.content,
            "chunks": document.chunks,
            "metadata": document.metadata,
        }
        self.client.index(
            index=self.index_name,
            id=document.id,
            document=doc_body,
        )

    def delete_document(self, document_id: str) -> None:
        """Delete a document by ID."""
        try:
            self.client.delete(index=self.index_name, id=document_id)
        except Exception:
            # Document might not exist, that's okay
            pass

    def search(self, query: str, top_k: int = 10, **kwargs) -> List[dict]:
        """
        Perform keyword search using BM25.

        Args:
            query: Search query
            top_k: Number of results to return
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["content^2", "chunks"],  # Boost content field
                    "type": "best_fields",
                }
            },
            "size": top_k,
        }

        response = self.client.search(index=self.index_name, body=search_body)

        results = []
        for hit in response["hits"]["hits"]:
            results.append(
                {
                    "id": hit["_id"],
                    "score": hit["_score"],
                    "source": hit["_source"]["source"],
                    "file_path": hit["_source"]["file_path"],
                    "content": hit["_source"]["content"][:500],  # Truncate
                    "metadata": hit["_source"]["metadata"],
                }
            )

        return results

    def get_stats(self) -> dict:
        """Get backend statistics."""
        if not self.client.indices.exists(index=self.index_name):
            return {"document_count": 0}

        stats = self.client.count(index=self.index_name)
        return {
            "document_count": stats["count"],
            "index_name": self.index_name,
        }

    def clear(self) -> None:
        """Clear all documents from the index."""
        if self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
            print(f"Deleted index: {self.index_name}")

    def needs_embeddings(self) -> bool:
        """Keyword search doesn't need embeddings."""
        return False
