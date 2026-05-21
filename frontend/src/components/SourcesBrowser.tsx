import { useState, useEffect } from 'react'
import { listRawSources, getPaper, discoverCrossDomainConnections } from '../api'
import type { DateGroup, Paper, CrossDomainConnection } from '../types'

const DOMAIN_ICONS: Record<string, string> = {
  'cs.AI': '🤖', 'cs.CL': '💬', 'cs.LG': '📊', 'q-bio.BM': '🧬',
  'cs.CV': '👁️', 'cs.RO': '🦾', 'cs.SE': '💻', 'cs.CR': '🔒',
  'cs.DB': '🗄️', 'cs.IR': '🔍', 'cs.NE': '🧠', 'cs.HC': '🖱️',
  'stat.ML': '📈', 'q-bio.QM': '🔬', 'physics.data-an': '⚛️', 'math.ST': '📐',
}

interface SourcesBrowserProps {
  onAddReferences?: (papers: Array<{ id: string; title: string }>) => void
  activeReferences?: Map<string, { id: string; title: string }>
}

export function SourcesBrowser({ onAddReferences, activeReferences }: SourcesBrowserProps) {
  const [dateGroups, setDateGroups] = useState<DateGroup[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null)
  const [selectedForChat, setSelectedForChat] = useState<Map<string, string>>(new Map())

  // Cross-Domain Discovery scanner states
  const [scanMode, setScanMode] = useState<'full' | 'custom'>('full')
  const [customCategories, setCustomCategories] = useState<string[]>([])
  const [scanLoading, setScanLoading] = useState(false)
  const [scanResults, setScanResults] = useState<CrossDomainConnection[]>([])
  const [indexingOccurred, setIndexingOccurred] = useState(false)
  const [hasScanned, setHasScanned] = useState(false)

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
    setScanMode('full')
    setCustomCategories([])
    setScanResults([])
    setIndexingOccurred(false)
    setHasScanned(false)
    try {
      const paper = await getPaper(arxivId)
      setSelectedPaper(paper)
    } catch {
      // silent
    }
  }

  async function handleScanConnections() {
    if (!selectedPaper) return
    setScanLoading(true)
    setHasScanned(false)
    setScanResults([])
    setIndexingOccurred(false)

    // Target domains to scan
    const targetDomains = scanMode === 'full' 
      ? Object.keys(DOMAIN_ICONS)
      : customCategories

    // Find source domain of current paper
    const sourceDomain = selectedPaper.categories?.split(',')[0].trim() || 'cs.AI'

    try {
      const res = await discoverCrossDomainConnections(
        selectedPaper.arxiv_id,
        sourceDomain,
        targetDomains,
        5
      )
      setScanResults(res.connections || [])
      setIndexingOccurred(res.indexing_occurred || false)
      setHasScanned(true)
    } catch (err) {
      console.error(err)
    } finally {
      setScanLoading(false)
    }
  }

  function handleAddSelectedToChat() {
    if (onAddReferences && selectedForChat.size > 0) {
      const papersArray = Array.from(selectedForChat.entries()).map(([id, title]) => ({ id, title }))
      onAddReferences(papersArray)
      setSelectedForChat(new Map())
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
                    <span className="category-name">{cat.display_name}</span>
                    <span className="category-count">{cat.paper_count}</span>
                  </div>
                  <div className="papers-list">
                    {cat.papers.map(p => (
                      <div
                        key={p.arxiv_id}
                        className={`paper-item ${selectedForChat.has(p.arxiv_id) ? 'selected' : ''}`}
                        onClick={() => openPaper(p.arxiv_id)}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData('application/cris-paper', JSON.stringify({
                            arxiv_id: p.arxiv_id,
                            title: p.title,
                          }))
                          e.dataTransfer.effectAllowed = 'copy'
                          // Visual feedback: add drag class
                          ;(e.target as HTMLElement).classList.add('dragging')
                        }}
                        onDragEnd={(e) => {
                          (e.target as HTMLElement).classList.remove('dragging')
                        }}
                      >
                        <div className="paper-item-checkbox-wrapper" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            className="paper-item-checkbox"
                            title="Select paper as reference"
                            aria-label="Select paper as reference"
                            checked={selectedForChat.has(p.arxiv_id)}
                            onChange={(e) => {
                              setSelectedForChat(prev => {
                                const next = new Map(prev)
                                if (e.target.checked) {
                                  next.set(p.arxiv_id, p.title)
                                } else {
                                  next.delete(p.arxiv_id)
                                }
                                return next
                              })
                            }}
                          />
                        </div>
                        <div className="paper-item-content">
                          <div className="paper-item-title">{p.title}</div>
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
              <h3>{selectedPaper.title}</h3>
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
                <div className="paper-detail-value paper-abstract-full">{selectedPaper.abstract || ''}</div>
              </div>

              {/* Cross-Domain Discovery Scanner Section */}
              <div className="paper-detail-section scanner-section" style={{
                marginTop: '20px',
                paddingTop: '20px',
                borderTop: '1px solid var(--border-subtle)'
              }}>
                <div className="paper-detail-label" style={{ fontWeight: 600, fontSize: '0.9rem', color: '#ff7759', marginBottom: '10px' }}>
                  📡 Cross-Domain Connection Discovery Scanner
                </div>
                
                {/* Mode Selector */}
                <div style={{ display: 'flex', gap: '16px', marginBottom: '12px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', cursor: 'pointer' }}>
                    <input 
                      type="radio" 
                      name="scan-mode" 
                      checked={scanMode === 'full'} 
                      onChange={() => setScanMode('full')}
                    />
                    Full Scan (All Categories)
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', cursor: 'pointer' }}>
                    <input 
                      type="radio" 
                      name="scan-mode" 
                      checked={scanMode === 'custom'} 
                      onChange={() => setScanMode('custom')}
                    />
                    Custom Scan
                  </label>
                </div>

                {/* Custom Categories Multi-Select checkboxes */}
                {scanMode === 'custom' && (
                  <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', 
                    gap: '8px', 
                    marginBottom: '16px',
                    padding: '10px',
                    borderRadius: '8px',
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-subtle)',
                    maxHeight: '120px',
                    overflowY: 'auto'
                  }}>
                    {Object.keys(DOMAIN_ICONS).map(cat => (
                      <label key={cat} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', cursor: 'pointer' }}>
                        <input 
                          type="checkbox"
                          checked={customCategories.includes(cat)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setCustomCategories(prev => [...prev, cat])
                            } else {
                              setCustomCategories(prev => prev.filter(c => c !== cat))
                            }
                          }}
                        />
                        {DOMAIN_ICONS[cat]} {cat}
                      </label>
                    ))}
                  </div>
                )}

                {/* Scan Trigger Button */}
                <button
                  onClick={handleScanConnections}
                  disabled={scanLoading || (scanMode === 'custom' && customCategories.length === 0)}
                  style={{
                    background: 'var(--accent-coral)',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 'var(--radius-md)',
                    padding: '8px 16px',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    cursor: scanLoading || (scanMode === 'custom' && customCategories.length === 0) ? 'not-allowed' : 'pointer',
                    transition: 'opacity 0.15s ease',
                    width: '100%',
                    marginBottom: '16px'
                  }}
                >
                  {scanLoading ? 'Scanning domains for connections...' : 'Scan for Cross-Domain Connections'}
                </button>

                {/* Loading Status Indicator */}
                {scanLoading && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    padding: '12px',
                    background: 'rgba(124, 172, 248, 0.08)',
                    borderRadius: '8px',
                    border: '1px solid rgba(124, 172, 248, 0.2)',
                    fontSize: '0.8rem',
                    color: '#7cacf8',
                    animation: 'fadeIn 0.2s ease-out',
                    marginBottom: '16px'
                  }}>
                    <span style={{ fontSize: '1rem', animation: 'thinkingPulse 1.5s ease-in-out infinite' }}>📡</span>
                    <span>Running Cross-Domain Similarity Mapping (cold start may take ~10-15s)...</span>
                  </div>
                )}

                {/* Scan Results */}
                {scanResults.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                        Discovered Connections:
                      </div>
                      {indexingOccurred && (
                        <span style={{
                          fontSize: '0.65rem',
                          background: 'rgba(0, 230, 118, 0.12)',
                          color: '#00e676',
                          border: '1px solid rgba(0, 230, 118, 0.3)',
                          padding: '2px 6px',
                          borderRadius: '4px'
                        }}>
                          ⚡ On-the-fly Indexing Occurred
                        </span>
                      )}
                    </div>
                    {scanResults.map((conn) => (
                      <div key={conn.id} style={{
                        padding: '12px',
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '8px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                            {conn.title}
                          </span>
                          <span style={{
                            fontSize: '0.7rem',
                            background: 'rgba(255, 119, 89, 0.12)',
                            color: 'var(--accent-coral)',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            whiteSpace: 'nowrap'
                          }}>
                            {Math.round(conn.similarity * 100)}% Similarity
                          </span>
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                          arXiv ID: {conn.id} • Target Domain: {conn.domain}
                        </div>
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '4px 0 0 0', lineHeight: 1.4 }}>
                          {conn.abstract.substring(0, 180)}...
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {scanResults.length === 0 && !scanLoading && hasScanned && (
                  <div style={{ 
                    textAlign: 'center', 
                    padding: '16px', 
                    color: 'var(--text-tertiary)',
                    fontSize: '0.8rem'
                  }}>
                    No strong semantic connections found in chosen target domains.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      {selectedForChat.size > 0 && (
        <div className="library-selection-bar">
          <span className="selection-count">
            {selectedForChat.size} {selectedForChat.size === 1 ? 'paper' : 'papers'} selected
          </span>
          <button className="btn-add-to-chat" onClick={handleAddSelectedToChat}>
            Add to Chat References
          </button>
          <button className="btn-clear-selection" onClick={() => setSelectedForChat(new Map())}>
            Clear
          </button>
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
