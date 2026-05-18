import { useState, useEffect } from 'react'
import { getWikiStats, getEntities, getNotes, rebuildWiki } from '../api'
import type { WikiStats, Entity, Note } from '../types'

export function MemoryPanel() {
  const [stats, setStats] = useState<WikiStats | null>(null)
  const [entities, setEntities] = useState<Entity[]>([])
  const [notes, setNotes] = useState<Note[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const [s, e, n] = await Promise.all([getWikiStats(), getEntities(), getNotes()])
      setStats(s)
      setEntities(e.entities || [])
      setNotes(n.notes || [])
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  async function handleRebuild() {
    if (!confirm('Rebuild wiki summaries and graph?')) return
    try {
      await rebuildWiki()
      load()
    } catch {
      alert('Failed to rebuild wiki')
    }
  }

  if (loading) return <div className="memory-panel"><div className="loading-placeholder">Loading memory...</div></div>

  return (
    <div className="memory-panel">
      {stats && (
        <div className="memory-stats">
          <div className="memory-stat"><div className="memory-stat-value">{stats.sources}</div><div className="memory-stat-label">Sources</div></div>
          <div className="memory-stat"><div className="memory-stat-value">{stats.concepts}</div><div className="memory-stat-label">Concepts</div></div>
          <div className="memory-stat"><div className="memory-stat-value">{stats.entities}</div><div className="memory-stat-label">Entities</div></div>
          <div className="memory-stat"><div className="memory-stat-value">{stats.notes}</div><div className="memory-stat-label">Notes</div></div>
        </div>
      )}
      <div className="memory-entities">
        <h4>Extracted Entities</h4>
        <div className="entity-list">
          {entities.length === 0
            ? <div className="empty-state">No entities yet</div>
            : entities.map((e, i) => (
              <div key={i} className="entity-item">
                <span className={`entity-type ${e.type}`}>{e.type}</span>
                <span className="entity-name">{escapeHtml(e.name)}</span>
                <span className="entity-mentions">{e.mentions}</span>
              </div>
            ))}
        </div>
      </div>
      <div className="memory-notes">
        <h4>Conversation Notes</h4>
        <div className="note-list">
          {notes.length === 0
            ? <div className="empty-state">No notes yet</div>
            : notes.map((n, i) => (
              <div key={i} className="note-item">
                <div className="note-title">{escapeHtml(n.title)}</div>
                <div className="note-date">{n.date}</div>
              </div>
            ))}
        </div>
      </div>
      <button className="memory-rebuild-btn" onClick={handleRebuild}>
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
          <path d="M2 8a6 6 0 0111.47-2.47M14 8a6 6 0 01-11.47 2.47" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
          <path d="M14 2v4h-4M2 14v-4h4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        </svg>
        Rebuild Wiki
      </button>
    </div>
  )
}

function escapeHtml(text: string): string {
  const el = document.createElement('div')
  el.textContent = text
  return el.innerHTML
}
