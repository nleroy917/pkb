from typing import List, Optional

from elasticsearch import Elasticsearch

from pkb.core.models import Document
from pkb.search_backends.base import BaseSearchBackend


class ElasticsearchVectorBackend(BaseSearchBackend):
    """
    Elasticsearch backend for dense vector search.
    Stores chunk-level embeddings for similarity search.
    """

    def __init__(
        self,
        index_name: str = "pkb_vector",
        host: str = "localhost",
        port: int = 9200,
        embedding_dim: int = 384,  # all-MiniLM-L6-v2 dimension
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize Elasticsearch vector backend.

        Args:
            index_name: Name of the Elasticsearch index
            host: Elasticsearch host
            port: Elasticsearch port
            embedding_dim: Dimension of embeddings
            api_key: Optional API key for authentication
            username: Optional username for basic auth
            password: Optional password for basic auth
        """
        super().__init__(name=f"elasticsearch_vector_{index_name}")
        self.index_name = index_name
        self.host = host
        self.port = port
        self.embedding_dim = embedding_dim

        if api_key:
            self.client = Elasticsearch([f"http://{host}:{port}"], api_key=api_key)
        elif username and password:
            self.client = Elasticsearch(
                [f"http://{host}:{port}"], basic_auth=(username, password)
            )
        else:
            self.client = Elasticsearch([f"http://{host}:{port}"])

    def create_index(self) -> None:
        """Create Elasticsearch index with dense vector mapping."""
        if self.client.indices.exists(index=self.index_name):
            print(f"Index {self.index_name} already exists")
            return

        mappings = {
            "properties": {
                "doc_id": {"type": "keyword"},
                "chunk_id": {"type": "integer"},
                "source": {"type": "keyword"},
                "file_path": {"type": "keyword"},
                "chunk_text": {"type": "text"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": self.embedding_dim,
                    "index": True,
                    "similarity": "cosine",
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
        Index a document with chunk embeddings.

        Args:
            document: Document to index
            embeddings: List of embeddings (one per chunk)
        """
        if not embeddings:
            raise ValueError("Embeddings required for vector backend")

        if len(embeddings) != len(document.chunks):
            raise ValueError(
                f"Number of embeddings ({len(embeddings)}) must match "
                f"number of chunks ({len(document.chunks)})"
            )

        for chunk_id, (chunk_text, embedding) in enumerate(
            zip(document.chunks, embeddings)
        ):
            chunk_doc = {
                "doc_id": document.id,
                "chunk_id": chunk_id,
                "source": document.source,
                "file_path": document.file_path,
                "chunk_text": chunk_text,
                "embedding": embedding,
                "metadata": document.metadata,
            }

            es_id = f"{document.id}_{chunk_id}"

            self.client.index(
                index=self.index_name,
                id=es_id,
                document=chunk_doc,
            )

    def delete_document(self, document_id: str) -> None:
        """
        Delete all chunks for a document.
        """
        self.client.delete_by_query(
            index=self.index_name, body={"query": {"term": {"doc_id": document_id}}}
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
        query_embedding: Optional[List[float]] = None,
        **kwargs,
    ) -> List[dict]:
        """
        Perform vector similarity search.

        Args:
            query: Search query (used for display only)
            top_k: Number of results to return
            query_embedding: Pre-computed query embedding (required)
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        if not query_embedding:
            raise ValueError("query_embedding required for vector search")

        # perform KNN search
        # note that k is the number of nearest neighbors to return
        # while num_candidates is the number of candidates to consider
        search_body = {
            "knn": {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": top_k,
                "num_candidates": top_k * 2,  # Consider more candidates
            },
            "_source": [
                "doc_id",
                "chunk_id",
                "source",
                "file_path",
                "chunk_text",
                "metadata",
            ],
        }

        response = self.client.search(index=self.index_name, body=search_body)

        results = []
        for hit in response["hits"]["hits"]:
            results.append(
                {
                    "id": hit["_source"]["doc_id"],
                    "chunk_id": hit["_source"]["chunk_id"],
                    "score": hit["_score"],
                    "source": hit["_source"]["source"],
                    "file_path": hit["_source"]["file_path"],
                    "content": hit["_source"]["chunk_text"],
                    "metadata": hit["_source"]["metadata"],
                }
            )

        return results

    def get_stats(self) -> dict:
        """
        Get backend statistics.
        """
        if not self.client.indices.exists(index=self.index_name):
            # print warning
            print(f"Index {self.index_name} does not exist")
            return {"chunk_count": 0, "document_count": 0}

        stats = self.client.count(index=self.index_name)

        # count unique documents
        agg_response = self.client.search(
            index=self.index_name,
            body={
                "size": 0,
                "aggs": {"unique_docs": {"cardinality": {"field": "doc_id"}}},
            },
        )

        return {
            "chunk_count": stats["count"],
            "document_count": agg_response["aggregations"]["unique_docs"]["value"],
            "index_name": self.index_name,
        }

    def clear(self) -> None:
        """
        Clear all documents from the index.
        """
        if self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
            print(f"Deleted index: {self.index_name}")

    def needs_embeddings(self) -> bool:
        """
        Vector search requires embeddings.
        """
        return True
