import { useState, useEffect } from 'react'
import { listRawSources, getPaper } from '../api'
import type { DateGroup, Paper } from '../types'

const DOMAIN_ICONS: Record<string, string> = {
  'cs.AI': '🤖', 'cs.CL': '💬', 'cs.LG': '📊', 'q-bio.BM': '🧬',
  'cs.CV': '👁️', 'cs.RO': '🦾', 'cs.SE': '💻', 'cs.CR': '🔒',
  'cs.DB': '🗄️', 'cs.IR': '🔍', 'cs.NE': '🧠', 'cs.HC': '🖱️',
  'stat.ML': '📈', 'q-bio.QM': '🔬', 'physics.data-an': '⚛️', 'math.ST': '📐',
}

export function SourcesBrowser() {
  const [dateGroups, setDateGroups] = useState<DateGroup[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const data = await listRawSources()
      setDateGroups(data.date_groups || [])
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  function toggleDate(date: string) {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(date)) next.delete(date)
      else next.add(date)
      return next
    })
  }

  async function openPaper(arxivId: string) {
    try {
      const paper = await getPaper(arxivId)
      setSelectedPaper(paper)
    } catch {
      // silent
    }
  }

  if (loading) return <div className="sources-browser"><div className="loading-placeholder">Loading papers...</div></div>
  if (dateGroups.length === 0) {
    return (
      <div className="sources-browser">
        <div className="empty-state">
          No papers ingested yet.
          <p style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 8 }}>
            Run: <code>python scripts/ingest_arxiv.py --days-back 1</code>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="sources-browser">
      <div className="sources-header">
        <span className="sources-count">{dateGroups.reduce((a, g) => a + g.paper_count, 0)} papers</span>
      </div>
      {dateGroups.map(dg => (
        <div key={dg.date} className="date-group">
          <div className="date-group-header" onClick={() => toggleDate(dg.date)}>
            <div>
              <div className="date-group-title">{dg.date}</div>
              <div className="date-group-subtitle">{dg.paper_count} papers • {dg.categories.length} categories</div>
            </div>
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" style={{ transform: expanded.has(dg.date) ? 'rotate(90deg)' : 'none', transition: 'transform 120ms' }}>
              <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
            </svg>
          </div>
          {expanded.has(dg.date) && (
            <div className="date-group-content">
              {dg.categories.map(cat => (
                <div key={cat.category} className="category-group">
                  <div className="category-header">
                    <span className="category-icon">{DOMAIN_ICONS[cat.category] || '📄'}</span>
                    <span className="category-name">{escapeHtml(cat.display_name)}</span>
                    <span className="category-count">{cat.paper_count}</span>
                  </div>
                  <div className="papers-list">
                    {cat.papers.map(p => (
                      <div key={p.arxiv_id} className="paper-item" onClick={() => openPaper(p.arxiv_id)}>
                        <div className="paper-item-content">
                          <div className="paper-item-title">{escapeHtml(p.title)}</div>
                          <div className="paper-item-meta">
                            <span className="paper-item-id">{p.arxiv_id}</span>
                            <span className="paper-item-authors">
                              {(p.authors || []).slice(0, 2).join(', ')}{(p.authors || []).length > 2 ? ' et al.' : ''}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {selectedPaper && (
        <div className="paper-modal visible">
          <div className="paper-modal-overlay" onClick={() => setSelectedPaper(null)} />
          <div className="paper-modal-content">
            <div className="paper-modal-header">
              <h3>{escapeHtml(selectedPaper.title)}</h3>
              <button className="close-modal-btn" onClick={() => setSelectedPaper(null)}>
                <svg width="18" height="18" viewBox="0 0 22 22" fill="currentColor">
                  <path d="M6 6l10 10M16 6L6 16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <div className="paper-modal-body">
              <div className="paper-detail-section">
                <div className="paper-detail-label">arXiv ID</div>
                <div className="paper-detail-value">{selectedPaper.arxiv_id}</div>
              </div>
              <div className="paper-detail-section">
                <div className="paper-detail-label">Authors</div>
                <div className="paper-detail-value">{(selectedPaper.authors || []).join(', ')}</div>
              </div>
              <div className="paper-detail-section">
                <div className="paper-detail-label">Categories</div>
                <div className="paper-detail-value">{selectedPaper.categories || 'N/A'}</div>
              </div>
              <div className="paper-detail-section">
                <div className="paper-detail-label">Published</div>
                <div className="paper-detail-value">{selectedPaper.created || 'N/A'}</div>
              </div>
              <div className="paper-detail-section">
                <div className="paper-detail-label">Abstract</div>
                <div className="paper-detail-value paper-abstract-full">{escapeHtml(selectedPaper.abstract || '')}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function escapeHtml(text: string): string {
  const el = document.createElement('div')
  el.textContent = text
  return el.innerHTML
}
