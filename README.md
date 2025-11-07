# PKB - Personal Knowledge Base

Search your Obsidian notes and Zotero PDFs using keyword and semantic search.

## Quick Start

### 1. Install

```bash
uv pip install -e .
```

### 2. Set Up Elasticsearch

You'll need Elasticsearch running locally. Follow the [official setup guide](https://www.elastic.co/guide/en/elasticsearch/reference/current/install-elasticsearch.html).

### 3. Configure PKB

Create your config file:

```bash
pkb init
```

Edit `~/.pkb/config.yaml`:

```yaml
sources:
  obsidian:
    enabled: true
    vault_path: ~/Documents/ObsidianVault  # Path to your vault
  zotero:
    enabled: false  # Set to true if you use Zotero
    csv_path: ~/Zotero/export.csv

backends:
  elasticsearch:
    enabled: true
    host: localhost
    port: 9200
    api_key: YOUR_API_KEY  # Optional, if needed
```

### 4. Index Your Files

Scan your Obsidian vault (or Zotero library):

```bash
pkb index
```

This creates a database of your files and tracks changes.

### 5. Load into Search Backends

Load your documents into Elasticsearch:

```bash
pkb load
```

This processes your files, generates embeddings, and loads them into both keyword (BM25) and vector (semantic) search indexes.

### 6. Search

**Via CLI:**

```bash
pkb search "machine learning"
pkb search "neural networks" --backend vector
pkb search "transformers" -k 20 -v
```

**Via REST API:**

Start the server:

```bash
pkb serve
```

Then visit http://localhost:8000/docs to test the API interactively, or use it from your frontend:

```javascript
const response = await fetch('http://localhost:8000/search?query=machine+learning');
const data = await response.json();
console.log(data.results);
```

## Commands

```bash
pkb init              # Create config file
pkb index             # Scan and index your files
pkb load              # Load into search backends
pkb search "query"    # Search from command line
pkb serve             # Start REST API server
pkb status            # Show indexing statistics
pkb clear             # Clear index (requires confirmation)
```

## How It Works

1. **Index**: Scans your files, detects changes (added/modified/deleted), and stores metadata
2. **Load**: Chunks documents, generates embeddings, and loads into Elasticsearch
3. **Search**: Queries using keyword (BM25) or semantic (vector) search

PKB only re-processes files that have changed, making updates fast.

## Advanced Usage

### Search Options

```bash
# Backend selection
pkb search "query" --backend keyword  # BM25 only
pkb search "query" --backend vector   # Semantic only
pkb search "query" --backend all      # Both (default)

# Limit results
pkb search "query" -k 5               # Top 5 results

# Verbose output
pkb search "query" -v                 # Show full content
```

### Server Options

```bash
pkb serve --host 0.0.0.0 --port 8080  # Custom host/port
pkb serve --reload                    # Auto-reload for development
```

### Incremental Updates

After modifying files:

```bash
pkb index   # Detects only changed files
pkb load    # Re-loads everything (working on incremental load)
```

### Force Re-index

```bash
pkb index --force   # Re-index all files
```

## Configuration

All settings in `~/.pkb/config.yaml`:

- **Data sources**: Obsidian vault path, Zotero CSV path
- **Indexing**: Chunk size, overlap, minimum chunk size
- **Embeddings**: Model selection (default: all-MiniLM-L6-v2)
- **Backends**: Elasticsearch connection details
- **Server**: Host and port settings

## Troubleshooting

**Elasticsearch connection failed:**
- Check if Elasticsearch is running: `curl http://localhost:9200`
- Verify credentials in config (API key or username/password)

**No results found:**
- Run `pkb status` to check if files are indexed
- Run `pkb load` to ensure backends are populated
- Check `/health` endpoint if using the server

**Import errors:**
- Install server dependencies: `uv pip install fastapi uvicorn`
- Install embedding dependencies: `uv pip install sentence-transformers torch`

## Architecture

```
Data Sources (Obsidian, Zotero)
    ↓
State Tracking (SQLite)
    ↓
Document Processing (Chunking)
    ↓
Embedding Generation (sentence-transformers)
    ↓
Search Backends (Elasticsearch: keyword + vector)
    ↓
Search Interface (CLI / REST API)
```

## What's Next

- Incremental loading (only load changed documents)
- Qdrant backend support
- Hybrid search (combine keyword + vector scores)
- Document deletion from backends
- More data sources (files, PDFs, web pages)