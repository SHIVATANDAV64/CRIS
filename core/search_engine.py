"""
Search Engine — SQLite FTS5 full-text search over wiki entries.
Provides fast, relevant search without vector databases.
"""
import re
import sqlite3
from pathlib import Path
from typing import Optional

from rich.console import Console

from config.settings import DB_PATH, WIKI_DIR

console = Console()


def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get a SQLite connection with FTS5 support."""
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def create_index(db_path: Optional[Path] = None):
    """Create the FTS5 search index tables."""
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    # Main papers table with metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            arxiv_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            contribution_type TEXT DEFAULT '',
            domains TEXT DEFAULT '',
            categories TEXT DEFAULT '',
            date_published TEXT DEFAULT '',
            wiki_content TEXT NOT NULL,
            cross_domain_tags TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # FTS5 virtual table for full-text search
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
            arxiv_id,
            title,
            wiki_content,
            domains,
            cross_domain_tags,
            contribution_type,
            content=papers,
            content_rowid=rowid
        )
    """)

    # Triggers to keep FTS in sync
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers BEGIN
            INSERT INTO papers_fts(rowid, arxiv_id, title, wiki_content, domains, cross_domain_tags, contribution_type)
            VALUES (new.rowid, new.arxiv_id, new.title, new.wiki_content, new.domains, new.cross_domain_tags, new.contribution_type);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers BEGIN
            INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, wiki_content, domains, cross_domain_tags, contribution_type)
            VALUES ('delete', old.rowid, old.arxiv_id, old.title, old.wiki_content, old.domains, old.cross_domain_tags, old.contribution_type);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE ON papers BEGIN
            INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, wiki_content, domains, cross_domain_tags, contribution_type)
            VALUES ('delete', old.rowid, old.arxiv_id, old.title, old.wiki_content, old.domains, old.cross_domain_tags, old.contribution_type);
            INSERT INTO papers_fts(rowid, arxiv_id, title, wiki_content, domains, cross_domain_tags, contribution_type)
            VALUES (new.rowid, new.arxiv_id, new.title, new.wiki_content, new.domains, new.cross_domain_tags, new.contribution_type);
        END
    """)

    conn.commit()
    conn.close()
    console.print("[green]Search index created/verified[/green]")


def _parse_wiki_frontmatter(wiki_content: str) -> dict:
    """Extract structured fields from wiki markdown frontmatter."""
    result = {
        "contribution_type": "",
        "domains": "",
        "cross_domain_tags": "",
    }

    # Extract contribution_type
    match = re.search(r'contribution_type:\s*(.+)', wiki_content)
    if match:
        result["contribution_type"] = match.group(1).strip()

    # Extract domains
    match = re.search(r'domains:\s*\[(.+?)\]', wiki_content)
    if match:
        result["domains"] = match.group(1).strip()

    # Extract cross-domain tags from [[wiki-links]]
    tags = re.findall(r'\[\[(.+?)\]\]', wiki_content)
    result["cross_domain_tags"] = ", ".join(set(tags))

    return result


def add_entry(
    arxiv_id: str,
    title: str,
    wiki_content: str,
    categories: str = "",
    date_published: str = "",
    db_path: Optional[Path] = None,
):
    """Add or update a wiki entry in the search index."""
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    # Parse structured fields from wiki content
    parsed = _parse_wiki_frontmatter(wiki_content)

    cursor.execute("""
        INSERT OR REPLACE INTO papers
        (arxiv_id, title, contribution_type, domains, categories, date_published, wiki_content, cross_domain_tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        arxiv_id,
        title,
        parsed["contribution_type"],
        parsed["domains"],
        categories,
        date_published,
        wiki_content,
        parsed["cross_domain_tags"],
    ))

    conn.commit()
    conn.close()


def search(query: str, limit: int = 20, db_path: Optional[Path] = None) -> list[dict]:
    """
    Full-text search across wiki entries.

    Args:
        query: Search query string
        limit: Maximum results to return

    Returns:
        List of matching paper dicts with wiki_content and relevance
    """
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        # Sanitize query: remove FTS5 special chars and build OR-based search
        import re as _re
        clean = _re.sub(r'[^\w\s]', ' ', query)  # Remove all non-alphanumeric
        words = [w for w in clean.split() if len(w) > 2]
        if words:
            fts_query = " OR ".join(words)
        else:
            fts_query = _re.sub(r'[^\w\s]', '', query) or "research"

        # FTS5 search with BM25 ranking
        cursor.execute("""
            SELECT
                p.arxiv_id,
                p.title,
                p.contribution_type,
                p.domains,
                p.categories,
                p.date_published,
                p.wiki_content,
                p.cross_domain_tags,
                rank
            FROM papers_fts
            JOIN papers p ON papers_fts.rowid = p.rowid
            WHERE papers_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_query, limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                "arxiv_id": row["arxiv_id"],
                "title": row["title"],
                "contribution_type": row["contribution_type"],
                "domains": row["domains"],
                "categories": row["categories"],
                "date_published": row["date_published"],
                "wiki_content": row["wiki_content"],
                "cross_domain_tags": row["cross_domain_tags"],
                "relevance": row["rank"],
            })
        return results

    except Exception as e:
        console.print(f"[red]Search error: {e}[/red]")
        return []
    finally:
        conn.close()


def search_by_tags(tags: list[str], limit: int = 20, db_path: Optional[Path] = None) -> list[dict]:
    """Search for papers containing specific cross-domain tags."""
    query = " OR ".join(tags)
    return search(query, limit, db_path)


def get_stats(db_path: Optional[Path] = None) -> dict:
    """Get statistics about the knowledge base."""
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    stats = {
        "total_papers": 0,
        "contribution_types": {},
        "top_domains": [],
    }

    try:
        cursor.execute("SELECT COUNT(*) FROM papers")
        stats["total_papers"] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT contribution_type, COUNT(*) as cnt
            FROM papers
            WHERE contribution_type != ''
            GROUP BY contribution_type
            ORDER BY cnt DESC
        """)
        stats["contribution_types"] = {row[0]: row[1] for row in cursor.fetchall()}

    except Exception:
        pass
    finally:
        conn.close()

    return stats


def get_all_entries(db_path: Optional[Path] = None) -> list[dict]:
    """Get all wiki entries (for browsing)."""
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT arxiv_id, title, contribution_type, domains, categories, wiki_content
            FROM papers
            ORDER BY date_published DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()
