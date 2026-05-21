<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(() => {
		goto('/chat');
	});
</script>

<p>Redirecting to chat...</p>

<style>
	p {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100vh;
		color: #888;
	}
</style>