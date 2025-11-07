#!/bin/bash
# Add required shadcn-svelte components

cd "$(dirname "$0")"

echo "Adding shadcn-svelte components..."

bunx shadcn-svelte@latest add input
bunx shadcn-svelte@latest add card
bunx shadcn-svelte@latest add badge

echo "Components added successfully!"