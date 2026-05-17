"""
Chat Memory Extractor — Extracts entities, facts, and claims from conversations
and feeds them into the Karpathy-style wiki structure.

Inspired by OpenHuman's conversation memory and Karpathy's wiki approach.
"""
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

from core.wiki_manager import WikiManager

console = Console()


class ChatMemoryExtractor:
    """Extracts memory from chat conversations and writes to wiki."""

    def __init__(self, wiki_manager: WikiManager):
        self.wiki_manager = wiki_manager

    def extract_from_conversation(
        self,
        user_message: str,
        assistant_response: str,
        session_id: str,
        sources: list[dict] | None = None,
    ) -> dict:
        """
        Extract entities, facts, and claims from a conversation exchange.

        Returns:
            Dict with extracted entities, facts, claims, and notes
        """
        result = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "entities": [],
            "facts": [],
            "claims": [],
            "notes": [],
            "concepts": [],
        }

        # Extract named entities (people, organizations, methods, etc.)
        result["entities"] = self._extract_entities(user_message, assistant_response)

        # Extract factual statements
        result["facts"] = self._extract_facts(assistant_response, sources)

        # Extract claims/insights that need verification
        result["claims"] = self._extract_claims(assistant_response)

        # Generate a note summarizing the conversation
        result["notes"] = self._generate_conversation_note(
            user_message, assistant_response, session_id
        )

        # Extract key concepts for concept pages
        result["concepts"] = self._extract_concepts(user_message, assistant_response)

        return result

    def _extract_entities(self, user_msg: str, assistant_msg: str) -> list[dict]:
        """Extract named entities from conversation."""
        entities = []

        # Pattern for potential entities: capitalized phrases, technical terms
        patterns = [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # Proper nouns
            r'\b[A-Z]{2,}\b',  # Acronyms
            r'[\w]+(?:\.[\w]+)+',  # Dotted notation (e.g., Transformer, BERT)
        ]

        combined_text = f"{user_msg} {assistant_msg}"

        for pattern in patterns:
            matches = re.findall(pattern, combined_text)
            for match in matches:
                # Filter out common words and short matches
                if len(match) > 2 and match.lower() not in [
                    'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have',
                    'been', 'are', 'was', 'were', 'but', 'not', 'you', 'all',
                    'can', 'had', 'her', 'she', 'his', 'how', 'its', 'may',
                    'new', 'now', 'old', 'see', 'two', 'way', 'who', 'did',
                    'get', 'let', 'say', 'too', 'use', 'CRIS', 'New', 'Chat',
                ]:
                    entities.append({
                        "name": match,
                        "type": self._classify_entity(match),
                        "mentions": combined_text.lower().count(match.lower()),
                    })

        # Deduplicate
        seen = set()
        unique_entities = []
        for e in entities:
            if e["name"] not in seen:
                seen.add(e["name"])
                unique_entities.append(e)

        return unique_entities[:20]  # Limit to top 20

    def _classify_entity(self, entity: str) -> str:
        """Classify an entity type."""
        if re.match(r'^[A-Z]{2,}$', entity):
            return "acronym"
        if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+', entity):
            return "concept"
        if entity.endswith(('tion', 'sion', 'ment', 'ness', 'ity')):
            return "concept"
        return "term"

    def _extract_facts(self, assistant_msg: str, sources: list[dict] | None) -> list[dict]:
        """Extract factual statements from assistant response."""
        facts = []

        # Look for factual patterns
        fact_patterns = [
            r'(?:is|are|was|were)\s+(?:a|an|the)?\s*([^.]+)',
            r'(?:demonstrates|shows|reveals|indicates)\s+(?:that)?\s*([^.]+)',
            r'(?:uses|employs|applies)\s+(?:the)?\s*([^.]+)',
        ]

        for pattern in fact_patterns:
            matches = re.findall(pattern, assistant_msg, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if len(match) > 10 and len(match) < 200:
                    facts.append({
                        "statement": match,
                        "confidence": "medium",
                        "source": sources[0]["arxiv_id"] if sources else None,
                    })

        return facts[:10]  # Limit to top 10

    def _extract_claims(self, assistant_msg: str) -> list[dict]:
        """Extract claims/insights that may need verification."""
        claims = []

        # Look for claim patterns
        claim_patterns = [
            r'(?:suggests|implies|indicates)\s+(?:that)?\s*([^.]+)',
            r'(?:could|may|might)\s+(?:be|have|provide)\s*([^.]+)',
            r'(?:potential|possible|likely)\s+([^.]+)',
        ]

        for pattern in claim_patterns:
            matches = re.findall(pattern, assistant_msg, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if len(match) > 10 and len(match) < 200:
                    claims.append({
                        "claim": match,
                        "verification_status": "pending",
                    })

        return claims[:10]

    def _generate_conversation_note(
        self, user_msg: str, assistant_msg: str, session_id: str
    ) -> dict:
        """Generate a summary note for the conversation."""
        # Create a concise summary
        user_preview = user_msg[:100] + ("..." if len(user_msg) > 100 else "")
        assistant_preview = assistant_msg[:200] + ("..." if len(assistant_msg) > 200 else "")

        return {
            "title": f"Conversation {session_id[:8]}",
            "summary": f"User asked: {user_preview}\n\nResponse: {assistant_preview}",
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
        }

    def _extract_concepts(self, user_msg: str, assistant_msg: str) -> list[dict]:
        """Extract key concepts for concept pages."""
        concepts = []

        # Look for concept patterns
        concept_patterns = [
            r'\[\[(.+?)\]\]',  # Wiki-style links
            r'\*\*(.+?)\*\*',  # Bold terms
            r'`([^`]+)`',  # Code terms
        ]

        combined_text = f"{user_msg} {assistant_msg}"

        for pattern in concept_patterns:
            matches = re.findall(pattern, combined_text)
            for match in matches:
                if len(match) > 2 and len(match) < 50:
                    concepts.append({
                        "name": match,
                        "description": f"Extracted from conversation on {datetime.now().strftime('%Y-%m-%d')}",
                    })

        # Deduplicate
        seen = set()
        unique_concepts = []
        for c in concepts:
            if c["name"] not in seen:
                seen.add(c["name"])
                unique_concepts.append(c)

        return unique_concepts[:15]

    def write_to_wiki(self, extraction: dict) -> dict:
        """Write extracted memory to wiki structure."""
        results = {
            "entities_written": 0,
            "notes_written": 0,
            "concepts_written": 0,
        }

        # Write entities
        for entity in extraction["entities"]:
            entity_path = self.wiki_manager.entities_dir / f"{self._slugify(entity['name'])}.md"
            if not entity_path.exists():
                fm = {
                    "name": entity["name"],
                    "type": entity["type"],
                    "mentions": entity["mentions"],
                    "first_seen": extraction["timestamp"],
                    "source": "chat_memory",
                    "session_id": extraction["session_id"],
                }
                content = f"---\n"
                content += f"  name: {entity['name']}\n"
                content += f"  type: {entity['type']}\n"
                content += f"  mentions: {entity['mentions']}\n"
                content += f"  first_seen: {extraction['timestamp']}\n"
                content += f"  source: chat_memory\n"
                content += f"  session_id: {extraction['session_id']}\n"
                content += f"---\n\n"
                content += f"# {entity['name']}\n\n"
                content += f"**Type:** {entity['type']}\n"
                content += f"**Mentions:** {entity['mentions']}\n"
                content += f"**First seen:** {extraction['timestamp']}\n\n"
                content += f"## Context\n\n"
                content += f"Extracted from chat conversation.\n"

                entity_path.write_text(content, encoding="utf-8")
                results["entities_written"] += 1

        # Write conversation note
        note = extraction["notes"]
        if note:
            note_path = self.wiki_manager.notes_dir / f"chat_{extraction['session_id'][:8]}.md"
            fm = {
                "title": note["title"],
                "date": note["timestamp"],
                "source": "chat_memory",
                "session_id": note["session_id"],
            }
            content = f"---\n"
            content += f"  title: {note['title']}\n"
            content += f"  date: {note['timestamp']}\n"
            content += f"  source: chat_memory\n"
            content += f"  session_id: {note['session_id']}\n"
            content += f"---\n\n"
            content += f"# {note['title']}\n\n"
            content += f"{note['summary']}\n"

            note_path.write_text(content, encoding="utf-8")
            results["notes_written"] += 1

        # Write concepts
        for concept in extraction["concepts"]:
            concept_path = self.wiki_manager.concepts_dir / f"{self._slugify(concept['name'])}.md"
            if not concept_path.exists():
                fm = {
                    "name": concept["name"],
                    "description": concept["description"],
                    "created": extraction["timestamp"],
                    "source": "chat_memory",
                }
                content = f"---\n"
                content += f"  name: {concept['name']}\n"
                content += f"  description: {concept['description']}\n"
                content += f"  created: {extraction['timestamp']}\n"
                content += f"  source: chat_memory\n"
                content += f"---\n\n"
                content += f"# {concept['name']}\n\n"
                content += f"{concept['description']}\n"

                concept_path.write_text(content, encoding="utf-8")
                results["concepts_written"] += 1

        return results

    def _slugify(self, text: str) -> str:
        """Convert text to a safe filename."""
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '_', text)
        return text.strip('_')


def extract_and_store_memory(
    user_message: str,
    assistant_response: str,
    session_id: str,
    wiki_dir: Path,
    sources: list[dict] | None = None,
) -> dict:
    """
    Main function to extract memory from conversation and store in wiki.

    Args:
        user_message: The user's query
        assistant_response: The assistant's response
        session_id: The chat session ID
        wiki_dir: Path to the wiki directory
        sources: List of source papers used

    Returns:
        Dict with extraction results
    """
    wiki_manager = WikiManager(wiki_dir)
    extractor = ChatMemoryExtractor(wiki_manager)

    # Extract memory
    extraction = extractor.extract_from_conversation(
        user_message, assistant_response, session_id, sources
    )

    # Write to wiki
    results = extractor.write_to_wiki(extraction)

    console.print(f"[green]Memory extracted: {results}[/green]")

    return {
        "extraction": extraction,
        "results": results,
    }
