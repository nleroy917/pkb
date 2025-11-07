<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';

	interface SearchResult {
		id: string;
		score: number;
		source: string;
		file_path: string;
		content: string;
		metadata: Record<string, any>;
		backend: string;
		chunk_id?: number;
	}

	interface SearchResponse {
		query: string;
		backend: string;
		total_results: number;
		results: SearchResult[];
	}

	let query = $state('');
	let backend = $state('all');
	let results = $state<SearchResult[]>([]);
	let loading = $state(false);
	let error = $state('');

	const API_URL = 'http://localhost:8000';

	async function search() {
		if (!query.trim()) {
			error = 'Please enter a search query';
			return;
		}

		loading = true;
		error = '';
		results = [];

		try {
			const response = await fetch(
				`${API_URL}/search?query=${encodeURIComponent(query)}&backend=${backend}&top_k=10`
			);

			if (!response.ok) {
				throw new Error(`Search failed: ${response.statusText}`);
			}

			const data: SearchResponse = await response.json();
			results = data.results;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Search failed';
			results = [];
		} finally {
			loading = false;
		}
	}

	function handleKeyPress(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			search();
		}
	}
</script>

<div class="container mx-auto max-w-4xl p-8">
	<div class="mb-8">
		<h1 class="mb-2 text-4xl font-bold">PKB Search</h1>
		<p class="text-muted-foreground">Search your personal knowledge base</p>
	</div>

	<Card class="mb-8">
		<CardContent class="pt-6">
			<div class="flex gap-2">
				<Input
					type="text"
					bind:value={query}
					placeholder="Search your notes and documents..."
					onkeypress={handleKeyPress}
					class="flex-1"
				/>
				<select bind:value={backend} class="rounded-md border px-3 py-2">
					<option value="all">All</option>
					<option value="keyword">Keyword</option>
					<option value="vector">Vector</option>
				</select>
				<Button onclick={search} disabled={loading}>
					{loading ? 'Searching...' : 'Search'}
				</Button>
			</div>
		</CardContent>
	</Card>

	{#if error}
		<Card class="mb-4 border-destructive">
			<CardContent class="pt-6">
				<p class="text-destructive">{error}</p>
			</CardContent>
		</Card>
	{/if}

	{#if results.length > 0}
		<div class="mb-4">
			<h2 class="text-xl font-semibold">Found {results.length} results</h2>
		</div>

		<div class="space-y-4">
			{#each results as result, i}
				<Card>
					<CardHeader>
						<div class="flex items-start justify-between">
							<div class="flex-1">
								<CardTitle class="text-lg">{result.file_path}</CardTitle>
								<CardDescription class="mt-1">
									<div class="flex flex-wrap gap-2">
										<Badge variant="secondary">Score: {result.score.toFixed(4)}</Badge>
										<Badge variant="outline">{result.source}</Badge>
										<Badge variant="outline">{result.backend.split('_')[1]}</Badge>
										{#if result.chunk_id !== null && result.chunk_id !== undefined}
											<Badge variant="outline">Chunk {result.chunk_id}</Badge>
										{/if}
									</div>
								</CardDescription>
							</div>
						</div>
					</CardHeader>
					<CardContent>
						<p class="text-sm leading-relaxed">
							{result.content.length > 400
								? result.content.substring(0, 400) + '...'
								: result.content}
						</p>
						{#if Object.keys(result.metadata).length > 0}
							<div class="mt-4 flex flex-wrap gap-2">
								{#each Object.entries(result.metadata) as [key, value]}
									<Badge variant="outline" class="text-xs">
										{key}: {value}
									</Badge>
								{/each}
							</div>
						{/if}
					</CardContent>
				</Card>
			{/each}
		</div>
	{/if}
</div>