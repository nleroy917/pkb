# PKB Frontend

Simple SvelteKit + shadcn-svelte UI for searching your personal knowledge base.

## Development

```bash
# Install dependencies
bun install

# Add shadcn components (if needed)
bunx shadcn-svelte@latest add input
bunx shadcn-svelte@latest add card
bunx shadcn-svelte@latest add badge

# Start dev server
bun run dev
```

## Building

```bash
# Build for production
bun run build

# Or use the helper script from the root directory
cd ..
./build-frontend.sh
```

The build output goes to `frontend/build/` and is automatically served by the FastAPI server when you run `pkb serve`.

## Features

- Clean, minimal search interface
- Real-time search with the PKB API
- Backend selection (keyword/vector/all)
- Result cards showing:
  - File path
  - Relevance score
  - Source (obsidian/zotero)
  - Backend used
  - Content preview
  - Metadata tags

## API Integration

The frontend connects to the PKB API at `http://localhost:8000/search`.

Make sure the backend server is running:
```bash
pkb serve
```