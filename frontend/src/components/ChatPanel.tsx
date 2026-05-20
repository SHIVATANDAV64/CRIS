import { useState, useRef, useEffect } from 'react'
import { renderMarkdown } from '../utils/markdown'
import { webSearch, scrapeUrl } from '../api'
import type { Message, SearchResult } from '../types'

interface ChatPanelProps {
  messages: Message[]
  onSend: (message: string) => void
  droppedPapers: Map<string, { id: string; title: string }>
  onPaperDrop: (id: string, title: string) => void
  onPaperRemove: (id: string) => void
  onToggleSidebar: () => void
  searchStatus?: string
}

export function ChatPanel({ messages, onSend, droppedPapers, onPaperDrop, onPaperRemove, onToggleSidebar, searchStatus }: ChatPanelProps) {
  const [input, setInput] = useState('')
  const [isDragOver, setIsDragOver] = useState(false)
  const [webSearchVisible, setWebSearchVisible] = useState(false)
  const [webSearchQuery, setWebSearchQuery] = useState('')
  const [webResults, setWebResults] = useState<SearchResult[]>([])
  const [webLoading, setWebLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  function handleSend() {
    const msg = input.trim()
    if (!msg) return
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    onSend(msg)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }

  async function handleWebSearch() {
    if (!webSearchQuery.trim()) return
    setWebLoading(true)
    try {
      const results = await webSearch(webSearchQuery, 5)
      setWebResults(results)
    } catch {
      setWebResults([])
    } finally {
      setWebLoading(false)
    }
  }

  async function handleScrape(url: string) {
    try {
      const data = await scrapeUrl(url)
      if (data.status === 'success') {
        setWebResults([{ title: data.title, url, snippet: data.content?.substring(0, 500) || '' }])
      }
    } catch {
      // silent
    }
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const arxivId = e.dataTransfer.getData('text/plain')
    const title = e.dataTransfer.getData('text/title') || arxivId
    if (arxivId) onPaperDrop(arxivId, title)
  }

  const isStreaming = messages.length > 0 && messages[messages.length - 1].role === 'assistant' && !messages[messages.length - 1].content

  return (
    <main className="chat-main">
      <header className="chat-header">
        <button className="menu-btn" onClick={onToggleSidebar}>
          <svg width="20" height="20" viewBox="0 0 22 22" fill="currentColor">
            <path d="M4 6h14M4 11h14M4 16h14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
          </svg>
        </button>
        <div className="header-title">
          <h2>Cross-Domain Research Assistant</h2>
          <span className="header-subtitle">wiki-style knowledge synthesis</span>
        </div>
        <button className="header-search-btn" onClick={() => setWebSearchVisible(v => !v)} title="Web Search">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
            <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.5" fill="none" />
            <path d="M13.5 13.5L17 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </header>

      {webSearchVisible && (
        <div className="web-search-panel">
          <div className="web-search-input">
            <input
              value={webSearchQuery}
              onChange={e => setWebSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleWebSearch()}
              placeholder="Search the web..."
            />
            <button onClick={handleWebSearch}>
              <svg width="14" height="14" viewBox="0 0 18 18" fill="currentColor">
                <circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
                <path d="M12 12l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>
          {webLoading && (
            <div className="web-search-results">
              <div className="skeleton-message">
                <div className="skeleton-avatar skeleton"></div>
                <div className="skeleton-content">
                  <div className="skeleton skeleton-line long"></div>
                  <div className="skeleton skeleton-line medium"></div>
                  <div className="skeleton skeleton-line short"></div>
                </div>
              </div>
              <div className="skeleton-message">
                <div className="skeleton-avatar skeleton"></div>
                <div className="skeleton-content">
                  <div className="skeleton skeleton-line long"></div>
                  <div className="skeleton skeleton-line medium"></div>
                </div>
              </div>
            </div>
          )}
          {!webLoading && webResults.length > 0 && (
            <div className="web-search-results">
              {webResults.map((r, i) => (
                <div key={i} className="web-search-result">
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="web-search-result-title"
                    style={{ color: '#7cacf8', textDecoration: 'none', cursor: 'pointer' }}
                  >
                    {escapeHtml(r.title)}
                  </a>
                  <div className="web-search-result-url">{escapeHtml(r.url)}</div>
                  {(r as any).combined_score !== undefined && (
                    <span className="relevance-badge" style={{
                      display: 'inline-block',
                      fontSize: '10px',
                      padding: '2px 6px',
                      margin: '4px 0',
                      borderRadius: '4px',
                      background: ((r as any).combined_score > 0.6 ? 'rgba(0,200,83,0.15)' : (r as any).combined_score > 0.4 ? 'rgba(255,200,0,0.15)' : 'rgba(255,100,100,0.15)'),
                      color: ((r as any).combined_score > 0.6 ? '#00c853' : (r as any).combined_score > 0.4 ? '#ffc800' : '#ff6464'),
                      border: `1px solid ${((r as any).combined_score > 0.6 ? 'rgba(0,200,83,0.3)' : (r as any).combined_score > 0.4 ? 'rgba(255,200,0,0.3)' : 'rgba(255,100,100,0.3)')}`
                    }}>
                      Relevance: {Math.round(((r as any).combined_score || 0) * 100)}%
                    </span>
                  )}
                  <div className="web-search-result-snippet">{escapeHtml(r.snippet).substring(0, 150)}...</div>
                  <button
                    className="web-result-use-btn"
                    style={{
                      marginTop: '4px', padding: '2px 10px', fontSize: '11px',
                      background: 'rgba(124,172,248,0.15)', border: '1px solid rgba(124,172,248,0.3)',
                      borderRadius: '4px', color: '#7cacf8', cursor: 'pointer',
                    }}
                    onClick={() => setInput(prev => prev + (prev ? '\n' : '') + `[${r.title}](${r.url}): ${r.snippet.substring(0, 200)}`)}
                  >
                    Use in chat
                  </button>
                </div>
              ))}
            </div>
          )}
          {!webLoading && webResults.length === 0 && webSearchQuery && (
            <div className="web-search-results"><div className="empty-state">No results found</div></div>
          )}
        </div>
      )}

      <div className="chat-messages" onDragOver={handleDragOver} onDrop={handleDrop}>
        {messages.length === 0 && (
          <div className="message system-message">
            <div className="message-content">
              <div className="welcome-card">
                <h2>Welcome to CRIS</h2>
                <p>Your cross-domain research intelligence assistant. I discover connections between scientific disciplines by reasoning over a curated knowledge base.</p>
                <div className="welcome-features">
                  <div className="feature"><span className="feature-icon">🔬</span><span>Cross-domain mechanism mapping</span></div>
                  <div className="feature"><span className="feature-icon">🧠</span><span>Multi-step reasoning with self-correction</span></div>
                  <div className="feature"><span className="feature-icon">📚</span><span>Wiki-powered knowledge that compounds</span></div>
                  <div className="feature"><span className="feature-icon">🌐</span><span>Web search for real-time research</span></div>
                </div>
                <p className="welcome-hint">Try asking a cross-domain question →</p>
              </div>
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`message ${msg.role}-message`}>
            <div className="message-content">
              {msg.role === 'assistant' && (
                <button
                  className="copy-btn"
                  onClick={() => {
                    navigator.clipboard.writeText(msg.content)
                    const btn = document.activeElement as HTMLButtonElement
                    if (btn) {
                      btn.classList.add('copied')
                      btn.textContent = 'Copied'
                      setTimeout(() => { btn.classList.remove('copied'); btn.textContent = 'Copy' }, 1500)
                    }
                  }}
                >
                  Copy
                </button>
              )}
              <div className="message-label">{msg.role === 'user' ? 'You' : 'CRIS'}</div>

              {msg.role === 'assistant' && msg.thinking && (
                <ThinkingBlock content={msg.thinking} />
              )}

              {msg.role === 'assistant' && msg.content ? (
                <div className="message-text" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
              ) : msg.role === 'assistant' && !msg.content ? (
                <div className="skeleton-message">
                  <div className="skeleton-avatar skeleton"></div>
                  <div className="skeleton-content">
                    <div className="skeleton skeleton-line long"></div>
                    <div className="skeleton skeleton-line medium"></div>
                    <div className="skeleton skeleton-line short"></div>
                  </div>
                </div>
              ) : (
                <div className="message-text">{escapeHtml(msg.content)}</div>
              )}

              {msg.sources && msg.sources.length > 0 && (
                <div className="sources-section">
                  <div className="sources-title">
                    Sources ({msg.sources.filter(s => s.contribution_type !== 'Web' && s.contribution_type !== 'News').length} papers
                    {msg.sources.filter(s => s.contribution_type === 'Web' || s.contribution_type === 'News').length > 0 &&
                      `, ${msg.sources.filter(s => s.contribution_type === 'Web' || s.contribution_type === 'News').length} web`})
                  </div>
                  {msg.sources.map((s, i) => (
                    s.contribution_type === 'Web' || s.contribution_type === 'News' ? (
                      <a
                        key={i}
                        className={`source-chip source-web ${s.contribution_type === 'News' ? 'source-news' : ''}`}
                        href={s.url || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={s.title || s.arxiv_id}
                        style={{
                          textDecoration: 'none',
                          cursor: 'pointer',
                          borderColor: s.contribution_type === 'News' ? 'rgba(248,172,89,0.4)' : 'rgba(124,172,248,0.4)',
                        }}
                      >
                        <span className={`source-type ${s.contribution_type}`}>{s.contribution_type}</span>
                        {s.arxiv_id}
                      </a>
                    ) : (
                      <span key={i} className="source-chip">
                        {s.contribution_type && <span className={`source-type ${s.contribution_type}`}>{s.contribution_type}</span>}
                        {s.arxiv_id}
                      </span>
                    )
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {searchStatus && (
          <div className="search-status-indicator" style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '8px 16px', margin: '0 auto 12px', maxWidth: '720px',
            background: 'rgba(124,172,248,0.08)', border: '1px solid rgba(124,172,248,0.2)',
            borderRadius: '8px', fontSize: '0.82rem', color: '#7cacf8',
            animation: 'fadeIn 0.2s ease-out',
          }}>
            <span style={{ fontSize: '1rem', animation: 'thinkingPulse 1.5s ease-in-out infinite' }}>🌐</span>
            {searchStatus}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div
        className={`chat-input-area ${isDragOver ? 'drag-over' : ''}`}
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes('application/cris-paper')) {
            e.preventDefault()
            e.dataTransfer.dropEffect = 'copy'
            setIsDragOver(true)
          }
        }}
        onDragLeave={(e) => {
          // Only hide if leaving the container (not entering a child)
          if (!e.currentTarget.contains(e.relatedTarget as Node)) {
            setIsDragOver(false)
          }
        }}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragOver(false)
          const paperData = e.dataTransfer.getData('application/cris-paper')
          if (paperData) {
            try {
              const { arxiv_id, title } = JSON.parse(paperData)
              onPaperDrop(arxiv_id, title)
            } catch {
              // invalid data
            }
          }
        }}
      >
        {isDragOver && (
          <div className="drop-overlay">
            <span className="drop-overlay-icon">📄</span>
            <span className="drop-overlay-text">Drop paper to add as reference</span>
          </div>
        )}
        {droppedPapers.size > 0 && (
          <div className="dropped-papers" style={{ display: 'flex' }}>
            {Array.from(droppedPapers.entries()).map(([id, paper]) => (
              <span key={id} className="dropped-paper-chip">
                <span className="chip-id">{id}</span>
                <span className="chip-title">{escapeHtml(paper.title.substring(0, 40))}...</span>
                <button className="chip-remove" onClick={() => onPaperRemove(id)}>
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="currentColor">
                    <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                  </svg>
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="input-container">
          <textarea
            ref={textareaRef}
            id="chat-input"
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Ask a cross-domain research question..."
            rows={1}
          />
          <button className="send-btn" onClick={handleSend} disabled={!input.trim() || isStreaming}>
            <svg width="18" height="18" viewBox="0 0 22 22" fill="none">
              <path d="M4 11L18 4L11 18L10 12L4 11Z" fill="currentColor" />
            </svg>
          </button>
        </div>
        <p className="input-hint">Enter to send • Shift+Enter for new line • Ctrl+N new chat • Ctrl+E export</p>
      </div>
    </main>
  )
}

function ThinkingBlock({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(true)
  return (
    <div className="thinking-section" style={{ display: 'block' }}>
      <button className={`thinking-toggle ${expanded ? 'expanded' : ''}`} onClick={() => setExpanded(v => !v)}>
        <span className="arrow">▶</span>
        <span>Reasoning trace</span>
      </button>
      <div className={`thinking-content ${expanded ? 'visible' : ''}`}>
        {escapeHtml(content)}
      </div>
    </div>
  )
}

function escapeHtml(text: string): string {
  const el = document.createElement('div')
  el.textContent = text
  return el.innerHTML
}
