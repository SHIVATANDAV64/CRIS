"""
Chat Store — Persistent chat session and message storage in SQLite.

Stores conversations across server restarts with proper session management.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from config.settings import DB_PATH


def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get a SQLite connection."""
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_chat_store(db_path: Optional[Path] = None):
    """Create chat session and message tables."""
    conn = _get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_count INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            thinking TEXT DEFAULT '',
            sources TEXT DEFAULT '[]',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_session
        ON chat_messages(session_id, timestamp)
    """)

    conn.commit()
    conn.close()


def create_session(session_id: str, title: str = "New Chat") -> dict:
    """Create a new chat session."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR IGNORE INTO chat_sessions (id, title) VALUES (?, ?)",
        (session_id, title)
    )
    conn.commit()

    session = {
        "id": session_id,
        "title": title,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "message_count": 0,
    }
    conn.close()
    return session


def get_session(session_id: str) -> Optional[dict]:
    """Get a session by ID."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def update_session_title(session_id: str, title: str):
    """Update a session's title."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (title, session_id)
    )
    conn.commit()
    conn.close()


def delete_session(session_id: str):
    """Delete a session and all its messages."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def list_sessions(limit: int = 50, offset: int = 0) -> list[dict]:
    """List all sessions, ordered by most recently updated."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title, created_at, updated_at, message_count
        FROM chat_sessions
        ORDER BY updated_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset)
    )
    sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return sessions


def add_message(
    session_id: str,
    role: str,
    content: str,
    thinking: str = "",
    sources: list[dict] | None = None,
) -> int:
    """
    Add a message to a session.

    Returns:
        The message ID
    """
    conn = _get_connection()
    cursor = conn.cursor()

    sources_json = json.dumps(sources or [])

    cursor.execute(
        """
        INSERT INTO chat_messages (session_id, role, content, thinking, sources)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, role, content, thinking, sources_json)
    )

    cursor.execute(
        """
        UPDATE chat_sessions
        SET updated_at = CURRENT_TIMESTAMP,
            message_count = message_count + 1
        WHERE id = ?
        """,
        (session_id,)
    )

    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return message_id


def get_messages(session_id: str, limit: int = 100) -> list[dict]:
    """Get all messages for a session, ordered by timestamp."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, session_id, role, content, thinking, sources, timestamp
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY timestamp ASC
        LIMIT ?
        """,
        (session_id, limit)
    )

    messages = []
    for row in cursor.fetchall():
        msg = dict(row)
        try:
            msg["sources"] = json.loads(msg["sources"]) if msg["sources"] else []
        except (json.JSONDecodeError, TypeError):
            msg["sources"] = []
        messages.append(msg)

    conn.close()
    return messages


def get_recent_messages(session_id: str, count: int = 6) -> list[dict]:
    """Get the most recent N messages for context building."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, content, thinking
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (session_id, count)
    )

    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return list(reversed(messages))


def format_history_for_prompt(session_id: str, max_exchanges: int = 3) -> str:
    """Format recent conversation history as context for the model."""
    messages = get_recent_messages(session_id, count=max_exchanges * 2)
    if not messages:
        return ""

    lines = ["## Recent Conversation Context", ""]
    for msg in messages:
        label = "Researcher" if msg["role"] == "user" else "CRIS"
        content_preview = msg["content"][:500]
        lines.append(f"**{label}:** {content_preview}")
        lines.append("")

    return "\n".join(lines)
