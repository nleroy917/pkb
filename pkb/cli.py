import sys

from pathlib import Path

import click

from rich.console import Console
from rich.table import Table

from pkb.config import Config
from pkb.data_sources import ObsidianDataSource, ZoteroDataSource
from pkb.indexing import DocumentProcessor, IndexManager

console = Console()


@click.group()
@click.option("--config", "-c", type=click.Path(), help="Path to config file")
@click.pass_context
def cli(ctx, config):
    """PKB - Personal Knowledge Base indexing and search system."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config(config) if config else Config()


@cli.command()
@click.option(
    "--source", "-s", type=str, help="Specific source to index (zotero, obsidian)"
)
@click.option("--force", "-f", is_flag=True, help="Force full reindex (ignore state)")
@click.option("--no-process", is_flag=True, help="Skip document processing (chunking)")
@click.pass_context
def index(ctx, source, force, no_process):
    """
    Index data sources and detect changes.

    Scans configured data sources, detects changes (added/modified/deleted),
    extracts content, and updates the state tracking database.
    """
    config = ctx.obj["config"]

    if source:
        sources_to_index = [source] if source in ["zotero", "obsidian"] else []
        if not sources_to_index:
            console.print(f"[red]Error:[/red] Unknown source '{source}'")
            console.print("Available sources: zotero, obsidian")
            sys.exit(1)
    else:
        sources_to_index = config.get_enabled_sources()

    if not sources_to_index:
        console.print("[yellow]Warning:[/yellow] No sources enabled in config")
        console.print("Edit your config at:", config.config_path)
        sys.exit(0)

    # initialize index manager
    state_db_path = config.get("indexing.state_db_path", "~/.pkb/state.db")
    chunk_size = config.get("indexing.chunk_size", 512)
    chunk_overlap = config.get("indexing.chunk_overlap", 50)
    min_chunk_size = config.get("indexing.min_chunk_size", 100)

    processor = DocumentProcessor(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        min_chunk_size=min_chunk_size,
    )
    manager = IndexManager(state_store_path=state_db_path, processor=processor)

    console.print("\n[bold]PKB Indexing[/bold]")
    console.print(f"Config: {config.config_path}")
    console.print(f"State DB: {state_db_path}\n")

    # index each source
    total_added = 0
    total_modified = 0
    total_deleted = 0

    for source_name in sources_to_index:
        console.print(f"[bold cyan]{source_name.upper()}[/bold cyan]")

        try:
            # create data source
            data_source = _create_data_source(source_name, config)

            # index or reindex
            if force:
                result = manager.reindex_source(
                    data_source, process_documents=not no_process
                )
            else:
                result = manager.index_source(
                    data_source, process_documents=not no_process
                )

            # update totals
            summary = result["summary"]
            total_added += summary["added"]
            total_modified += summary["modified"]
            total_deleted += summary["deleted"]

            # display results
            _print_index_results(source_name, summary, result["documents"])

        except Exception as e:
            console.print(f"[red]Error indexing {source_name}:[/red] {e}")
            continue

    console.print("\n[bold]Summary[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Added", style="green")
    table.add_column("Modified", style="yellow")
    table.add_column("Deleted", style="red")
    table.add_row(str(total_added), str(total_modified), str(total_deleted))
    console.print(table)


@cli.command()
@click.option(
    "--backend", "-b", type=str, help="Specific backend to load (keyword, vector)"
)
@click.option("--source", "-s", type=str, help="Only load documents from this source")
@click.pass_context
def load(ctx, backend, source):
    """
    Load indexed documents into search backends.

    Re-extracts documents from data sources and loads them into
    the specified search backend with embeddings.
    """
    config = ctx.obj["config"]

    # import here to avoid circular dependencies
    from pkb.embeddings import EmbeddingGenerator
    from pkb.loading import BackendLoader
    from pkb.search_backends.elastic.keyword import ElasticsearchKeywordBackend
    from pkb.search_backends.elastic.vector import ElasticsearchVectorBackend

    # get enabled sources
    if source:
        sources_to_load = [source] if source in ["zotero", "obsidian"] else []
        if not sources_to_load:
            console.print(f"[red]Error:[/red] Unknown source '{source}'")
            sys.exit(1)
    else:
        sources_to_load = config.get_enabled_sources()

    if not sources_to_load:
        console.print("[yellow]Warning:[/yellow] No sources enabled in config")
        sys.exit(0)

    # create data sources
    data_sources = []
    for source_name in sources_to_load:
        try:
            ds = _create_data_source(source_name, config)
            data_sources.append(ds)
        except Exception as e:
            console.print(f"[red]Error creating {source_name}:[/red] {e}")
            continue

    if not data_sources:
        console.print("[red]No valid data sources available[/red]")
        sys.exit(1)

    # initialize components
    state_db_path = config.get("indexing.state_db_path", "~/.pkb/state.db")
    chunk_size = config.get("indexing.chunk_size", 512)
    chunk_overlap = config.get("indexing.chunk_overlap", 50)
    min_chunk_size = config.get("indexing.min_chunk_size", 100)

    processor = DocumentProcessor(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        min_chunk_size=min_chunk_size,
    )
    manager = IndexManager(state_store_path=state_db_path, processor=processor)

    embedding_model = config.get(
        "embeddings.model", "sentence-transformers/all-MiniLM-L6-v2"
    )
    embedding_gen = EmbeddingGenerator(model_name=embedding_model)

    loader = BackendLoader(index_manager=manager, embedding_generator=embedding_gen)

    # determine which backends to load
    backends_to_load = []

    # Get ES config
    es_config = config.get("backends.elasticsearch", {})
    es_api_key = es_config.get("api_key")
    es_username = es_config.get("username")
    es_password = es_config.get("password")

    if backend:
        # specific backend requested
        if backend == "keyword":
            backends_to_load.append(
                ElasticsearchKeywordBackend(
                    index_name=es_config.get("indexes", {}).get(
                        "keyword", "pkb_keyword"
                    ),
                    host=es_config.get("host", "localhost"),
                    port=es_config.get("port", 9200),
                    api_key=es_api_key,
                    username=es_username,
                    password=es_password,
                )
            )
        elif backend == "vector":
            backends_to_load.append(
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
        else:
            console.print(f"[red]Unknown backend:[/red] {backend}")
            console.print("Available: keyword, vector")
            sys.exit(1)
    else:
        # load all enabled backends
        if es_config.get("enabled", False):
            backends_to_load.append(
                ElasticsearchKeywordBackend(
                    index_name=es_config.get("indexes", {}).get(
                        "keyword", "pkb_keyword"
                    ),
                    host=es_config.get("host", "localhost"),
                    port=es_config.get("port", 9200),
                    api_key=es_api_key,
                    username=es_username,
                    password=es_password,
                )
            )
            backends_to_load.append(
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

    if not backends_to_load:
        console.print("[yellow]No backends to load[/yellow]")
        console.print("Specify --backend or enable backends in config")
        sys.exit(0)

    console.print(f"\n[bold]PKB Loading[/bold]")
    console.print(f"Sources: {', '.join(ds.source_name for ds in data_sources)}")
    console.print(f"Backends: {', '.join(b.name for b in backends_to_load)}\n")

    # load each backend
    for backend_instance in backends_to_load:
        try:
            loader.load_backend(
                backend=backend_instance,
                data_sources=data_sources,
                source_filter=source,
            )
        except Exception as e:
            console.print(f"[red]Error loading {backend_instance.name}:[/red] {e}")
            import traceback

            traceback.print_exc()
            continue

    console.print("\n[green]Loading complete![/green]")


@cli.command()
@click.argument("query")
@click.option(
    "--backend",
    "-b",
    type=click.Choice(["keyword", "vector", "all"]),
    default="all",
    help="Backend type to use for search",
)
@click.option("--top-k", "-k", type=int, default=10, help="Number of results to return")
@click.option("--verbose", "-v", is_flag=True, help="Show full content and metadata")
@click.pass_context
def search(ctx, query, backend, top_k, verbose):
    """
    Search across configured backends.

    Searches indexed documents using the specified backend(s).
    Results are ranked by relevance score.

    Example:
        pkb search "machine learning"
        pkb search "neural networks" --backend vector -k 5
    """
    config = ctx.obj["config"]

    # import here to avoid circular dependencies
    from pkb.embeddings import EmbeddingGenerator
    from pkb.search import SearchEngine
    from pkb.search_backends.elastic.keyword import ElasticsearchKeywordBackend
    from pkb.search_backends.elastic.vector import ElasticsearchVectorBackend

    # get ES config
    es_config = config.get("backends.elasticsearch", {})

    if not es_config.get("enabled", False):
        console.print(
            "[yellow]Warning:[/yellow] Elasticsearch backend not enabled in config"
        )
        console.print("Enable it in your config or use --backend to specify backends")
        sys.exit(0)

    es_api_key = es_config.get("api_key")
    es_username = es_config.get("username")
    es_password = es_config.get("password")

    # create backends based on selection
    backends = []

    if backend in ["keyword", "all"]:
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

    if backend in ["vector", "all"]:
        # need embedding generator for vector search
        embedding_model = config.get(
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

    if not backends:
        console.print("[red]No backends available[/red]")
        sys.exit(1)

    # create search engine
    embedding_gen = None
    if backend in ["vector", "all"]:
        embedding_model = config.get(
            "embeddings.model", "sentence-transformers/all-MiniLM-L6-v2"
        )
        embedding_gen = EmbeddingGenerator(model_name=embedding_model)

    search_engine = SearchEngine(backends=backends, embedding_generator=embedding_gen)

    console.print(f"\n[bold]Searching for:[/bold] {query}")
    console.print(f"Backend: {backend}, Top-K: {top_k}\n")

    try:
        results = search_engine.search(query, top_k=top_k)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        console.print(f"[green]Found {len(results)} results[/green]\n")

        # display results
        for i, result in enumerate(results, 1):
            console.print(f"[bold cyan]{i}. {result.file_path}[/bold cyan]")
            console.print(f"   Score: [yellow]{result.score:.4f}[/yellow]")
            console.print(f"   Source: {result.source}")
            console.print(f"   Backend: {result.backend}")

            if result.chunk_id is not None:
                console.print(f"   Chunk: {result.chunk_id}")

            # show content preview or full content
            if verbose:
                console.print(f"\n   Content:\n   {result.content}\n")
                if result.metadata:
                    console.print(f"   Metadata: {result.metadata}")
            else:
                # show first 200 chars
                preview = (
                    result.content[:200] + "..."
                    if len(result.content) > 200
                    else result.content
                )
                console.print(f"   {preview}")

            console.print()

    except Exception as e:
        console.print(f"[red]Search failed:[/red] {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option("--host", "-h", type=str, help="Server host")
@click.option("--port", "-p", type=int, help="Server port")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.pass_context
def serve(ctx, host, port, reload):
    """
    Start the REST API server.

    Starts a web server that provides a REST API for searching
    across all configured backends. Includes automatic CORS support
    for frontend applications.

    Example:
        pkb serve
        pkb serve --host 0.0.0.0 --port 8080
        pkb serve --reload  # Development mode with auto-reload
    """
    config = ctx.obj["config"]

    host = host or config.get("server.host", "0.0.0.0")
    port = port or config.get("server.port", 8000)

    # check if elasticsearch is enabled
    es_config = config.get("backends.elasticsearch", {})
    if not es_config.get("enabled", False):
        console.print(
            "[yellow]Warning:[/yellow] Elasticsearch backend not enabled in config"
        )
        console.print("The server will start but search will not work.")
        console.print("Enable Elasticsearch in your config file.\n")

    console.print("[bold]Starting PKB REST API Server[/bold]")
    console.print(f"Host: {host}")
    console.print(f"Port: {port}")
    console.print(f"Config: {config.config_path}\n")

    console.print("[green]Server will be available at:[/green]")
    console.print(f"  API: http://{host}:{port}")
    console.print(f"  Docs: http://{host}:{port}/docs")
    console.print(f"  Health: http://{host}:{port}/health\n")

    console.print("[cyan]Press Ctrl+C to stop the server[/cyan]\n")

    try:
        import uvicorn

        from pkb.server import create_app

        # create app with config
        app = create_app(config=config)

        # run server
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=reload,
            log_level="info",
        )

    except ImportError:
        console.print(
            "[red]Error:[/red] uvicorn and fastapi are required to run the server"
        )
        console.print("Install with: pip install fastapi uvicorn")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Server error:[/red] {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option("--source", "-s", type=str, help="Show status for specific source")
@click.pass_context
def status(ctx, source):
    """Show indexing status and statistics."""
    config = ctx.obj["config"]

    state_db_path = config.get("indexing.state_db_path", "~/.pkb/state.db")
    manager = IndexManager(state_store_path=state_db_path)

    console.print(f"\n[bold]PKB Status[/bold]")
    console.print(f"State DB: {state_db_path}\n")

    if source:
        status = manager.get_status(source=source)
        console.print(f"[bold cyan]{source.upper()}[/bold cyan]")
        console.print(f"  Total files: {status['total_files']}")
    else:
        status = manager.get_status()
        console.print(f"[bold]Total indexed files:[/bold] {status['total_files']}\n")

        if status["sources"]:
            table = Table(show_header=True, header_style="bold")
            table.add_column("Source")
            table.add_column("Files", justify="right")

            for source_name, count in status["sources"].items():
                table.add_row(source_name, str(count))

            console.print(table)
        else:
            console.print("[yellow]No sources indexed yet[/yellow]")


@cli.command()
@click.option("--source", "-s", type=str, help="Clear specific source")
@click.option("--all", "clear_all", is_flag=True, help="Clear all sources")
@click.confirmation_option(prompt="Are you sure you want to clear the index?")
@click.pass_context
def clear(ctx, source, clear_all):
    """
    Clear indexing state (requires confirmation).
    """
    config = ctx.obj["config"]

    state_db_path = config.get("indexing.state_db_path", "~/.pkb/state.db")
    manager = IndexManager(state_store_path=state_db_path)

    if clear_all:
        manager.clear_all()
        console.print("[green]Cleared all indexing state[/green]")
    elif source:
        count = manager.clear_source(source)
        console.print(f"[green]Cleared {count} files from {source}[/green]")
    else:
        console.print("[yellow]Specify --source or --all[/yellow]")


@cli.command()
@click.pass_context
def init(ctx):
    """
    Initialize PKB configuration.
    """
    config = ctx.obj["config"]

    if config.config_path.exists():
        console.print(f"[yellow]Config already exists:[/yellow] {config.config_path}")
        if not click.confirm("Overwrite?"):
            return

    config.config_path.parent.mkdir(parents=True, exist_ok=True)
    config.save()

    console.print(f"[green]Created config at:[/green] {config.config_path}")
    console.print("\nEdit the config to:")
    console.print("  1. Enable data sources (zotero, obsidian)")
    console.print("  2. Configure paths to your data")
    console.print("  3. Enable search backends")


def _create_data_source(source_name: str, config: Config):
    """
    Create a data source instance from config.
    """
    if source_name == "zotero":
        csv_path = config.get("sources.zotero.csv_path")
        csv_path = Path(csv_path).expanduser()
        return ZoteroDataSource(str(csv_path))

    elif source_name == "obsidian":
        vault_path = config.get("sources.obsidian.vault_path")
        vault_path = Path(vault_path).expanduser()
        return ObsidianDataSource(str(vault_path))

    else:
        raise ValueError(f"Unknown source: {source_name}")


def _print_index_results(source_name: str, summary: dict, documents: dict):
    """
    Print indexing results for a source.
    """
    console.print(f"  Added: [green]{summary['added']}[/green]")
    console.print(f"  Modified: [yellow]{summary['modified']}[/yellow]")
    console.print(f"  Deleted: [red]{summary['deleted']}[/red]")

    if documents:
        total_chunks = sum(len(doc.chunks) for doc in documents.values())
        console.print(f"  Processed: {len(documents)} documents, {total_chunks} chunks")

    console.print()


if __name__ == "__main__":
    cli()
