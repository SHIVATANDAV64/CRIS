"""
Wiki Compiler — Uses MiniMax M2.5 (Amazon Bedrock) to compile paper metadata
into structured wiki entries for cross-domain discovery.
"""
import time
from typing import Optional

from openai import OpenAI
from rich.console import Console

from config.settings import (
    BEDROCK_API_KEY,
    BEDROCK_BASE_URL,
    COMPILER_MODEL,
    COMPILER_MAX_TOKENS,
    COMPILER_TEMPERATURE,
)
from config.prompts import WIKI_COMPILER_SYSTEM, WIKI_COMPILER_USER

console = Console()


class WikiCompiler:
    """Compiles paper metadata into structured wiki entries using MiniMax M2.5 on Bedrock."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or BEDROCK_API_KEY
        if not key:
            raise ValueError(
                "BEDROCK_API_KEY not set. Add it to your .env file.\n"
                "Get a key from: https://console.aws.amazon.com/bedrock/"
            )

        self.client = OpenAI(
            base_url=BEDROCK_BASE_URL,
            api_key=key,
        )
        self.model = COMPILER_MODEL

    def compile_paper(self, paper: dict) -> Optional[str]:
        """
        Compile a single paper into a wiki entry.

        Args:
            paper: Dict with arxiv_id, title, abstract, authors, categories, created

        Returns:
            Wiki entry as markdown string, or None on failure
        """
        # Format the user message with paper details
        authors_list = [a for a in paper.get("authors", []) if a]
        authors_str = ", ".join(authors_list[:5])
        if len(authors_list) > 5:
            authors_str += f" et al. ({len(paper['authors'])} total)"

        user_message = WIKI_COMPILER_USER.format(
            arxiv_id=paper.get("arxiv_id", "unknown"),
            title=paper.get("title", ""),
            authors=authors_str,
            categories=paper.get("categories", ""),
            published=paper.get("created", ""),
            abstract=paper.get("abstract", ""),
        )

        max_retries = 3
        base_delay = 5.0

        for attempt in range(max_retries):
            try:
                # Use streaming since Bedrock has streaming enabled
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": WIKI_COMPILER_SYSTEM},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=COMPILER_MAX_TOKENS,
                    temperature=COMPILER_TEMPERATURE,
                    stream=True,
                )

                # Collect streamed chunks into full response
                content_parts = []
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content_parts.append(chunk.choices[0].delta.content)

                content = "".join(content_parts)
                if not content:
                    console.print(f"[yellow]Empty response for {paper.get('arxiv_id')}[/yellow]")
                    return None

                return content.strip()

            except Exception as e:
                error_str = str(e)
                if ("429" in error_str or "throttl" in error_str.lower()) and attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    console.print(f"    [yellow]Rate limited. Retrying in {sleep_time}s...[/yellow]")
                    time.sleep(sleep_time)
                else:
                    console.print(f"[red]Compilation error for {paper.get('arxiv_id')}: {e}[/red]")
                    return None

    def compile_batch(
        self,
        papers: list[dict],
        delay_seconds: float = 2.0,
        skip_existing_ids: Optional[set] = None,
    ) -> dict[str, str]:
        """
        Compile multiple papers into wiki entries.

        Args:
            papers: List of paper dicts
            delay_seconds: Delay between API calls (rate limiting)
            skip_existing_ids: Set of arxiv_ids to skip (already compiled)

        Returns:
            Dict mapping arxiv_id → wiki markdown string
        """
        skip = skip_existing_ids or set()
        results = {}

        to_compile = [p for p in papers if p.get("arxiv_id") not in skip]
        console.print(f"\n[cyan]Compiling {len(to_compile)} papers (skipping {len(skip)} existing)...[/cyan]")

        for i, paper in enumerate(to_compile):
            arxiv_id = paper.get("arxiv_id", "unknown")
            console.print(
                f"  [{i+1}/{len(to_compile)}] Compiling: [bold]{paper.get('title', '')[:60]}...[/bold]"
            )

            wiki_entry = self.compile_paper(paper)
            if wiki_entry:
                results[arxiv_id] = wiki_entry
                console.print(f"    [green]+ Done ({len(wiki_entry)} chars)[/green]")
            else:
                console.print(f"    [red]x Failed[/red]")

            # Rate limiting
            if i < len(to_compile) - 1:
                time.sleep(delay_seconds)

        console.print(f"\n[green]Compiled {len(results)}/{len(to_compile)} papers successfully[/green]")
        return results

