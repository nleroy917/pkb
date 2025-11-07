#!/bin/bash
# Build the frontend and prepare for serving

set -e

echo "Building PKB Frontend..."

# Navigate to frontend directory
cd frontend

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    bun install
fi

# Add required shadcn components if not already added
echo "Checking shadcn components..."
if [ ! -d "src/lib/components/ui/input" ]; then
    echo "Adding input component..."
    bunx shadcn-svelte@latest add input -y
fi

if [ ! -d "src/lib/components/ui/card" ]; then
    echo "Adding card component..."
    bunx shadcn-svelte@latest add card -y
fi

if [ ! -d "src/lib/components/ui/badge" ]; then
    echo "Adding badge component..."
    bunx shadcn-svelte@latest add badge -y
fi

# Build the app
echo "Building frontend..."
bun run build

cd ..

echo ""
echo "✅ Frontend built successfully!"
echo ""
echo "Run 'pkb serve' to start the server with the frontend"
echo "The UI will be available at http://localhost:8000"