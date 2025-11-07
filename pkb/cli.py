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
@click.option("--source", "-s", type=str, help="Specific source to index (zotero, obsidian)")
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
                result = manager.reindex_source(data_source, process_documents=not no_process)
            else:
                result = manager.index_source(data_source, process_documents=not no_process)

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
@click.option("--backend", "-b", type=str, help="Specific backend to load (elasticsearch, qdrant)")
@click.option("--source", "-s", type=str, help="Only load documents from this source")
@click.pass_context
def load(ctx, backend, source):
    """
    Load indexed documents into search backends.

    Takes documents from the indexing phase and loads them into
    configured search backends (Elasticsearch, Qdrant, etc.).
    """
    config = ctx.obj["config"]

    console.print("[yellow]Note:[/yellow] Backend loading not yet implemented")
    console.print("This will load documents into:")
    console.print("  - Elasticsearch (keyword, vector, semantic indexes)")
    console.print("  - Qdrant (vector database)")


@cli.command()
@click.option("--host", "-h", type=str, help="Server host")
@click.option("--port", "-p", type=int, help="Server port")
@click.pass_context
def serve(ctx, host, port):
    """
    Start the REST API server.

    Starts a web server that provides a REST API for searching
    across all configured backends.
    """
    config = ctx.obj["config"]

    host = host or config.get("server.host", "0.0.0.0")
    port = port or config.get("server.port", 8000)

    console.print("[yellow]Note:[/yellow] REST server not yet implemented")
    console.print(f"Will serve on http://{host}:{port}")


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