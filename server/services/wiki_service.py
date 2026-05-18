from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

from core.wiki_manager import WikiManager
from config.settings import WIKI_DIR


class WikiService:
    def __init__(self):
        self.wiki_dir = WIKI_DIR
        self.wiki_manager = WikiManager(self.wiki_dir)

    def get_stats(self) -> Dict[str, Any]:
        sources = self.wiki_manager.get_all_sources()
        notes = self.wiki_manager.get_notes()
        concepts = list(self.wiki_manager.concepts_dir.glob("*.md"))
        entities = list(self.wiki_manager.entities_dir.glob("*.md"))

        return {
            "sources": len(sources),
            "concepts": len(concepts),
            "entities": len(entities),
            "notes": len(notes),
            "last_updated": datetime.now().isoformat(),
        }

    def rebuild_all(self) -> None:
        self.wiki_manager.rebuild_all()

    def get_entities(self) -> List[Dict[str, Any]]:
        entities = []
        for f in self.wiki_manager.entities_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            fm, _ = self.wiki_manager.parse_frontmatter(content)
            entities.append({
                "name": fm.get("name", f.stem),
                "type": fm.get("type", "term"),
                "mentions": fm.get("mentions", 0),
                "first_seen": fm.get("first_seen", ""),
            })
        return entities

    def get_notes(self) -> List[Dict[str, Any]]:
        notes = []
        for f in self.wiki_manager.notes_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            fm, _ = self.wiki_manager.parse_frontmatter(content)
            notes.append({
                "title": fm.get("title", f.stem),
                "date": fm.get("date", ""),
                "session_id": fm.get("session_id", ""),
            })
        return notes
