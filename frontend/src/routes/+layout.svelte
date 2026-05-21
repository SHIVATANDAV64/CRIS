<script lang="ts">
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
</script>

<div class="app-container">
	<main class="main-content">
		{@render children()}
	</main>
</div>

<style>
	:global(*) {
		margin: 0;
		padding: 0;
		box-sizing: border-box;
	}

	:global(body) {
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
		background-color: #0f0f0f;
		color: #e0e0e0;
		min-height: 100vh;
	}

	.app-container {
		display: flex;
		min-height: 100vh;
	}

	.main-content {
		flex: 1;
		display: flex;
		flex-direction: column;
	}
</style>