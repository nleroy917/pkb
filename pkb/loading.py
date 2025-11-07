from typing import List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from pkb.core.models import Document
from pkb.data_sources.base import BaseDataSource
from pkb.embeddings import EmbeddingGenerator
from pkb.indexing import IndexManager
from pkb.search_backends.base import BaseSearchBackend

console = Console()


class BackendLoader:
    """
    Orchestrates loading documents from index into search backends.
    """

    def __init__(
        self,
        index_manager: IndexManager,
        embedding_generator: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize backend loader.

        Args:
            index_manager: Index manager for accessing indexed documents
            embedding_generator: Optional embedding generator (created if needed)
        """
        self.index_manager = index_manager
        self.embedding_generator = embedding_generator

    def load_backend(
        self,
        backend: BaseSearchBackend,
        data_sources: List[BaseDataSource],
        source_filter: Optional[str] = None,
    ) -> dict:
        """
        Load documents from data sources into a backend.

        Args:
            backend: Backend to load into
            data_sources: List of data sources to load from
            source_filter: Optional source name filter

        Returns:
            Dictionary with loading statistics
        """
        console.print(f"\n[bold]Loading {backend.name}[/bold]")

        console.print("  Creating index...")
        backend.create_index()
        console.print("  Extracting documents...")
        documents = []

        for data_source in data_sources:
            # skip if filtering and this isn't the right source
            if source_filter and data_source.source_name != source_filter:
                continue

            console.print(f"    Processing {data_source.source_name}...")

            # scan and extract documents
            for file_id, file_path in data_source.scan():
                try:
                    # extract content
                    content = data_source.extract_content(file_path)

                    # create document
                    doc = data_source.create_document(
                        file_id, file_path, content=content
                    )

                    # process (chunk) document
                    doc = self.index_manager.processor.process_document(doc)

                    documents.append(doc)

                except Exception as e:
                    console.print(
                        f"      [yellow]Warning: Failed to process {file_path}: {e}[/yellow]"
                    )
                    continue

        if not documents:
            console.print("  [yellow]No documents to load[/yellow]")
            return {"loaded": 0, "failed": 0}

        console.print(f"  Found {len(documents)} documents")

        embeddings_map = {}
        if backend.needs_embeddings():
            console.print("  Generating embeddings...")
            embeddings_map = self._generate_embeddings_for_documents(documents)

        console.print("  Loading documents...")
        loaded = 0
        failed = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading...", total=len(documents))

            for doc in documents:
                try:
                    embeddings = (
                        embeddings_map.get(doc.id)
                        if backend.needs_embeddings()
                        else None
                    )
                    backend.index_document(doc, embeddings=embeddings)
                    loaded += 1
                except Exception as e:
                    console.print(f"    [red]Failed to load {doc.id}:[/red] {e}")
                    failed += 1

                progress.advance(task)

        # get backend stats
        stats = backend.get_stats()

        console.print(f"  [green]Loaded: {loaded}[/green]")
        if failed > 0:
            console.print(f"  [red]Failed: {failed}[/red]")
        console.print(f"  Backend stats: {stats}")

        return {
            "loaded": loaded,
            "failed": failed,
            "stats": stats,
        }

    def _generate_embeddings_for_documents(self, documents: List[Document]) -> dict:
        """
        Generate embeddings for all document chunks.

        Args:
            documents: List of documents

        Returns:
            Dictionary mapping document IDs to list of embeddings
        """
        if self.embedding_generator is None:
            self.embedding_generator = EmbeddingGenerator()

        embeddings_map = {}

        all_chunks = []
        chunk_to_doc = []

        for doc in documents:
            for chunk in doc.chunks:
                all_chunks.append(chunk)
                chunk_to_doc.append(doc.id)

        if not all_chunks:
            return embeddings_map

        # generate embeddings in batch
        console.print(f"    Encoding {len(all_chunks)} chunks...")
        embeddings = self.embedding_generator.encode(
            all_chunks,
            batch_size=32,
            show_progress=True,
        )

        # group embeddings by document
        for doc_id, embedding in zip(chunk_to_doc, embeddings):
            if doc_id not in embeddings_map:
                embeddings_map[doc_id] = []
            embeddings_map[doc_id].append(embedding.tolist())

        return embeddings_map

    def clear_backend(self, backend: BaseSearchBackend) -> None:
        """
        Clear all documents from a backend.

        Args:
            backend: Backend to clear
        """
        console.print(f"[yellow]Clearing {backend.name}...[/yellow]")
        backend.clear()
        console.print("[green]Cleared[/green]")
