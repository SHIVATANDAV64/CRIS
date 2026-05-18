import type { Session } from '../types'
import { formatDate } from '../utils/format'

interface HistoryListProps {
  sessions: Session[]
  activeId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

export function HistoryList({ sessions, activeId, onSelect, onDelete }: HistoryListProps) {
  if (sessions.length === 0) {
    return <div className="history-list"><div className="empty-state">No conversations yet. Start a new chat!</div></div>
  }

  return (
    <div className="history-list">
      {sessions.map(s => (
        <div key={s.id} className={`history-item ${s.id === activeId ? 'active' : ''}`} onClick={() => onSelect(s.id)}>
          <div className="history-item-content">
            <div className="history-item-title">{escapeHtml(s.title)}</div>
            <div className="history-item-meta">{formatDate(s.updated_at)} • {s.message_count} messages</div>
          </div>
          <button className="history-delete-btn" onClick={(e) => { e.stopPropagation(); onDelete(s.id) }} title="Delete">
            <svg width="12" height="12" viewBox="0 0 14 14" fill="currentColor">
              <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  )
}

function escapeHtml(text: string): string {
  const el = document.createElement('div')
  el.textContent = text
  return el.innerHTML
}
