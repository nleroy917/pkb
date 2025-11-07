from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pkb.config import Config
from pkb.embeddings import EmbeddingGenerator
from pkb.search import SearchEngine
from pkb.search_backends.elastic.keyword import ElasticsearchKeywordBackend
from pkb.search_backends.elastic.vector import ElasticsearchVectorBackend


class SearchRequest(BaseModel):
    """Search request model."""

    query: str
    backend: Optional[str] = "all"
    top_k: Optional[int] = 10


class SearchResultResponse(BaseModel):
    """Search result response model."""

    id: str
    score: float
    source: str
    file_path: str
    content: str
    metadata: dict
    backend: str
    chunk_id: Optional[int] = None


class SearchResponse(BaseModel):
    """Search response model."""

    query: str
    backend: str
    total_results: int
    results: List[SearchResultResponse]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    backends: dict


class PKBServer:
    """
    REST API server for PKB search functionality.

    Provides endpoints for searching across configured backends.
    Designed to be used with frontend applications (e.g., Svelte).
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize PKB server.

        Args:
            config: PKB configuration (default: loads from default location)
        """
        self.config = config or Config()
        self.app = FastAPI(
            title="PKB Search API",
            description="Personal Knowledge Base search API",
            version="0.1.0",
        )

        # setup CORS for frontend access
        self._setup_cors()

        # initialize search engine
        self.search_engine = self._create_search_engine()

        # register routes
        self._register_routes()

    def _setup_cors(self):
        """Setup CORS middleware for frontend access."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins (customize for production)
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _create_search_engine(self) -> SearchEngine:
        """
        Create and configure search engine with backends.

        Returns:
            Configured SearchEngine instance
        """
        # get ES config
        es_config = self.config.get("backends.elasticsearch", {})

        if not es_config.get("enabled", False):
            print("Warning: Elasticsearch backend not enabled in config")
            return SearchEngine()

        es_api_key = es_config.get("api_key")
        es_username = es_config.get("username")
        es_password = es_config.get("password")

        # create backends
        backends = []

        # keyword backend
        backends.append(
            ElasticsearchKeywordBackend(
                index_name=es_config.get("indexes", {}).get("keyword", "pkb_keyword"),
                host=es_config.get("host", "localhost"),
                port=es_config.get("port", 9200),
                api_key=es_api_key,
                username=es_username,
                password=es_password,
            )
        )

        # vector backend
        embedding_model = self.config.get(
            "embeddings.model", "sentence-transformers/all-MiniLM-L6-v2"
        )
        embedding_gen = EmbeddingGenerator(model_name=embedding_model)

        backends.append(
            ElasticsearchVectorBackend(
                index_name=es_config.get("indexes", {}).get("vector", "pkb_vector"),
                host=es_config.get("host", "localhost"),
                port=es_config.get("port", 9200),
                embedding_dim=embedding_gen.get_embedding_dim(),
                api_key=es_api_key,
                username=es_username,
                password=es_password,
            )
        )

        return SearchEngine(backends=backends, embedding_generator=embedding_gen)

    def _register_routes(self):
        """Register API routes."""

        @self.app.get("/", tags=["General"])
        async def root():
            """Root endpoint with API information."""
            return {
                "name": "PKB Search API",
                "version": "0.1.0",
                "endpoints": {
                    "search": "/search",
                    "health": "/health",
                    "docs": "/docs",
                },
            }

        @self.app.get("/health", response_model=HealthResponse, tags=["General"])
        async def health():
            """
            Health check endpoint.

            Returns server status and backend statistics.
            """
            try:
                backend_stats = self.search_engine.get_backend_stats()
                return HealthResponse(status="ok", backends=backend_stats)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Health check failed: {e}")

        @self.app.get("/search", response_model=SearchResponse, tags=["Search"])
        async def search(
            query: str = Query(..., description="Search query"),
            backend: str = Query(
                "all", description="Backend type (keyword, vector, all)"
            ),
            top_k: int = Query(
                10, description="Number of results to return", ge=1, le=100
            ),
        ):
            """
            Search endpoint.

            Searches across configured backends and returns ranked results.

            Args:
                query: Search query string
                backend: Backend type to use (keyword, vector, all)
                top_k: Maximum number of results to return (1-100)

            Returns:
                Search results with scores and metadata
            """
            if not query or not query.strip():
                raise HTTPException(status_code=400, detail="Query cannot be empty")

            try:
                results = self.search_engine.search(
                    query=query,
                    backend_type=backend if backend != "all" else None,
                    top_k=top_k,
                )

                # convert to response format
                result_responses = [
                    SearchResultResponse(
                        id=r.id,
                        score=r.score,
                        source=r.source,
                        file_path=r.file_path,
                        content=r.content,
                        metadata=r.metadata,
                        backend=r.backend,
                        chunk_id=r.chunk_id,
                    )
                    for r in results
                ]

                return SearchResponse(
                    query=query,
                    backend=backend,
                    total_results=len(result_responses),
                    results=result_responses,
                )

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

        @self.app.post("/search", response_model=SearchResponse, tags=["Search"])
        async def search_post(request: SearchRequest):
            """
            Search endpoint (POST version).

            Alternative POST endpoint for search, useful for complex queries.

            Args:
                request: Search request with query and parameters

            Returns:
                Search results with scores and metadata
            """
            if not request.query or not request.query.strip():
                raise HTTPException(status_code=400, detail="Query cannot be empty")

            try:
                results = self.search_engine.search(
                    query=request.query,
                    backend_type=request.backend if request.backend != "all" else None,
                    top_k=request.top_k,
                )

                # convert to response format
                result_responses = [
                    SearchResultResponse(
                        id=r.id,
                        score=r.score,
                        source=r.source,
                        file_path=r.file_path,
                        content=r.content,
                        metadata=r.metadata,
                        backend=r.backend,
                        chunk_id=r.chunk_id,
                    )
                    for r in results
                ]

                return SearchResponse(
                    query=request.query,
                    backend=request.backend,
                    total_results=len(result_responses),
                    results=result_responses,
                )

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    def get_app(self) -> FastAPI:
        """
        Get the FastAPI application instance.

        Returns:
            FastAPI app instance
        """
        return self.app


def create_app(config: Optional[Config] = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        config: PKB configuration

    Returns:
        Configured FastAPI app
    """
    server = PKBServer(config=config)
    return server.get_app()
