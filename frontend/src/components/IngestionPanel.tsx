import { useState, useEffect, useRef } from 'react'
import { runIngestScript, getIngestStatus, stopIngestScript, IngestStatusDetails } from '../api'

const PRESETS = [
  { id: 'cs.AI', name: 'Artificial Intelligence (cs.AI)' },
  { id: 'cs.CL', name: 'Computation and Language (cs.CL)' },
  { id: 'cs.LG', name: 'Machine Learning (cs.LG)' },
  { id: 'cs.CV', name: 'Computer Vision (cs.CV)' },
  { id: 'cs.RO', name: 'Robotics (cs.RO)' },
  { id: 'cs.SE', name: 'Software Engineering (cs.SE)' },
  { id: 'cs.CR', name: 'Cryptography and Security (cs.CR)' },
  { id: 'cs.DB', name: 'Databases (cs.DB)' },
  { id: 'cs.IR', name: 'Information Retrieval (cs.IR)' },
  { id: 'cs.NE', name: 'Neural & Evolutionary (cs.NE)' },
  { id: 'cs.HC', name: 'Human-Computer Interaction (cs.HC)' },
  { id: 'stat.ML', name: 'Machine Learning Stats (stat.ML)' },
  { id: 'q-bio.BM', name: 'Biomolecules (q-bio.BM)' },
  { id: 'q-bio.QM', name: 'Quantitative Methods (q-bio.QM)' },
]

export function IngestionPanel() {
  const [date, setDate] = useState(() => {
    // Default to yesterday
    const yest = new Date(Date.now() - 86400000)
    return yest.toISOString().split('T')[0]
  })
  const [daysBack, setDaysBack] = useState(1)
  const [maxPapers, setMaxPapers] = useState(50)
  const [domainMode, setDomainMode] = useState(true)
  const [selectedCats, setSelectedCats] = useState<string[]>(['cs.AI', 'cs.CL', 'cs.LG'])
  const [customCats, setCustomCats] = useState('')
  const [running, setRunning] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [error, setError] = useState('')
  const [details, setDetails] = useState<IngestStatusDetails | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)

  // Scroll console to bottom on new logs
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [details?.logs])

  // Poll status on load and during ingestion
  useEffect(() => {
    let timer: number
    async function checkStatus() {
      try {
        const res = await getIngestStatus()
        setRunning(res.running)
        setDetails(res)
        if (res.running) {
          setStatusMessage(`Ingesting papers... (Fetched ${res.papers_fetched} papers)`)
        } else if (res.error) {
          setError(res.error)
          setStatusMessage('Ingestion task failed.')
        } else if (res.dates_processed > 0 && res.dates_processed === res.dates_total) {
          setStatusMessage(`Ingestion task completed successfully! Total papers added: ${res.papers_fetched}`)
        } else {
          setStatusMessage('')
        }
      } catch (err) {
        console.error('Failed to fetch status:', err)
      }
    }

    checkStatus()
    timer = window.setInterval(checkStatus, 1500)

    return () => {
      if (timer) clearInterval(timer)
    }
  }, [])

  const toggleCategory = (catId: string) => {
    setSelectedCats(prev =>
      prev.includes(catId) ? prev.filter(c => c !== catId) : [...prev, catId]
    )
  }

  const handleSelectAll = () => {
    setSelectedCats(PRESETS.map(p => p.id))
  }

  const handleClearAll = () => {
    setSelectedCats([])
  }

  const handleStart = async () => {
    setError('')
    setStatusMessage('')
    
    // Combine checked presets with custom categories
    const presetStr = selectedCats.join(',')
    const cleanCustom = customCats
      .split(',')
      .map(c => c.trim())
      .filter(c => c.length > 0)
      .join(',')

    const combinedCats = [presetStr, cleanCustom].filter(Boolean).join(',')

    if (!combinedCats) {
      setError('Please select at least one category or enter a custom one.')
      return
    }

    try {
      setRunning(true)
      setStatusMessage('Requesting background ingestion task to start...')
      const res = await runIngestScript({
        date: daysBack > 0 ? undefined : date,
        days_back: daysBack,
        categories: combinedCats,
        max_papers: maxPapers,
        domain_mode: domainMode,
      })
      setStatusMessage(res.message || 'arXiv paper ingestion started in the background.')
    } catch (err: any) {
      setError(err.message || 'Failed to start ingestion task.')
      setRunning(false)
    }
  }

  const handleStop = async () => {
    try {
      setStatusMessage('Stopping background ingestion task...')
      const res = await stopIngestScript()
      setStatusMessage(res.message || 'Stop request sent.')
    } catch (err: any) {
      setError(err.message || 'Failed to stop ingestion task.')
    }
  }

  return (
    <div className="ingestion-panel" style={{ flex: 1, padding: '24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '24px', color: 'var(--text-primary)', backgroundColor: 'var(--bg-primary)' }}>
      <div className="panel-header" style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>arXiv Paper Ingestion Control</h1>
        <p style={{ margin: '8px 0 0 0', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
          Manually ingest papers from arXiv to update your local research database and knowledge graph.
        </p>
      </div>

      <div className="ingestion-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
        {/* Left Settings Card */}
        <div className="card" style={{ backgroundColor: 'var(--bg-secondary)', borderRadius: '12px', border: '1px solid var(--border-subtle)', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: '0 0 8px 0', color: 'var(--text-primary)' }}>Configuration Settings</h2>
          
          <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)' }}>Days Back to Fetch</label>
            <input
              type="number"
              min="0"
              max="30"
              value={daysBack}
              onChange={e => setDaysBack(parseInt(e.target.value) || 0)}
              style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Set to 0 to target a specific date instead of a relative range.</span>
          </div>

          {daysBack === 0 && (
            <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)' }}>Target Date</label>
              <input
                type="date"
                value={date}
                onChange={e => setDate(e.target.value)}
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}
              />
            </div>
          )}

          <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)' }}>Max Papers Per Category</label>
            <input
              type="number"
              min="1"
              max="200"
              value={maxPapers}
              onChange={e => setMaxPapers(parseInt(e.target.value) || 10)}
              style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}
            />
          </div>

          <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
            <input
              type="checkbox"
              id="domainMode"
              checked={domainMode}
              onChange={e => setDomainMode(e.target.checked)}
              style={{ width: '16px', height: '16px', accentColor: 'var(--accent-blue)' }}
            />
            <label htmlFor="domainMode" style={{ fontSize: '0.875rem', fontWeight: 500, cursor: 'pointer', color: 'var(--text-secondary)' }}>
              Organize inside domain subfolders (e.g. cs_AI)
            </label>
          </div>

          <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)' }}>Custom arXiv Categories</label>
            <input
              type="text"
              placeholder="e.g. cs.NE,q-bio.NC,quant-ph.QM"
              value={customCats}
              onChange={e => setCustomCats(e.target.value)}
              style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Comma-separated codes. Will be fetched along with checkmarks.</span>
          </div>
        </div>

        {/* Right Preset Categories Card */}
        <div className="card" style={{ backgroundColor: 'var(--bg-secondary)', borderRadius: '12px', border: '1px solid var(--border-subtle)', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>ArXiv Domains</h2>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button 
                onClick={handleSelectAll} 
                style={{ padding: '4px 8px', fontSize: '0.75rem', border: '1px solid var(--border-subtle)', borderRadius: '4px', backgroundColor: 'var(--bg-primary)', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                All
              </button>
              <button 
                onClick={handleClearAll} 
                style={{ padding: '4px 8px', fontSize: '0.75rem', border: '1px solid var(--border-subtle)', borderRadius: '4px', backgroundColor: 'var(--bg-primary)', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                Clear
              </button>
            </div>
          </div>

          <div className="presets-list" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '8px', maxHeight: '280px', overflowY: 'auto', paddingRight: '4px' }}>
            {PRESETS.map(p => (
              <div 
                key={p.id} 
                onClick={() => toggleCategory(p.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: selectedCats.includes(p.id) ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-primary)',
                  borderColor: selectedCats.includes(p.id) ? 'var(--accent-blue)' : 'var(--border-subtle)',
                  cursor: 'pointer',
                  fontSize: '0.75rem',
                  fontWeight: selectedCats.includes(p.id) ? 500 : 400,
                  transition: 'all 0.15s ease'
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedCats.includes(p.id)}
                  onChange={() => {}} // Handled by div onClick
                  style={{ pointerEvents: 'none', accentColor: 'var(--accent-blue)' }}
                />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Trigger & Status Section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '12px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <button
            onClick={handleStart}
            disabled={running}
            style={{
              alignSelf: 'flex-start',
              padding: '12px 24px',
              fontSize: '0.95rem',
              fontWeight: 600,
              borderRadius: '8px',
              backgroundColor: running ? 'var(--bg-secondary)' : 'var(--accent-blue)',
              color: running ? 'var(--text-muted)' : '#ffffff',
              border: 'none',
              cursor: running ? 'not-allowed' : 'pointer',
              boxShadow: running ? 'none' : '0 4px 6px -1px rgba(59, 130, 246, 0.2)',
              transition: 'all 0.15s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            {running && (
              <svg className="animate-spin" style={{ width: '16px', height: '16px', border: '2px solid transparent', borderTopColor: 'currentColor', borderRadius: '50%' }} viewBox="0 0 24 24"></svg>
            )}
            {running ? 'Ingestion In Progress...' : 'Start Ingestion'}
          </button>

          {running && (
            <button
              onClick={handleStop}
              style={{
                alignSelf: 'flex-start',
                padding: '12px 24px',
                fontSize: '0.95rem',
                fontWeight: 600,
                borderRadius: '8px',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                color: '#ef4444',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.18)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'
              }}
            >
              Stop Ingestion
            </button>
          )}
        </div>

        {statusMessage && (
          <div style={{ padding: '12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-secondary)', color: 'var(--text-secondary)', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: running ? 'var(--accent-blue)' : 'var(--accent-emerald)' }}></span>
            {statusMessage}
          </div>
        )}

        {error && (
          <div style={{ padding: '12px', borderRadius: '6px', border: '1px solid rgba(239, 68, 68, 0.2)', backgroundColor: 'rgba(239, 68, 68, 0.05)', color: 'rgb(239, 68, 68)', fontSize: '0.875rem' }}>
            {error}
          </div>
        )}

        {/* Detailed Progress Container */}
        {details && (details.running || details.logs.length > 0) && (
          <div className="ingest-progress-container" style={{
            marginTop: '8px',
            backgroundColor: 'var(--bg-secondary)',
            borderRadius: '12px',
            border: '1px solid var(--border-subtle)',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>Ingestion Progress</span>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-blue)' }}>
                {details.dates_total > 0 ? `${Math.round((details.dates_processed / details.dates_total) * 100)}%` : '0%'}
              </span>
            </div>

            {/* Progress Bar */}
            <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-primary)', borderRadius: '4px', overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
              <div style={{
                width: `${details.dates_total > 0 ? (details.dates_processed / details.dates_total) * 100 : 0}%`,
                height: '100%',
                backgroundColor: 'var(--accent-blue)',
                borderRadius: '4px',
                transition: 'width 0.4s ease-out'
              }} />
            </div>

            {/* Stats Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '16px', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Status</div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600, color: details.running ? 'var(--accent-blue)' : 'var(--accent-emerald)' }}>
                  {details.running ? 'Running' : 'Completed'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Current Date</div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{details.current_date || 'N/A'}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Dates Processed</div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{details.dates_processed} / {details.dates_total}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Papers Fetched</div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{details.papers_fetched}</div>
              </div>
            </div>

            {/* Console Output */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Console Output</span>
                {details.running && (
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--accent-blue)', animation: 'pulse 1s infinite alternate' }} />
                    Live Updating...
                  </span>
                )}
              </div>
              
              <div style={{
                backgroundColor: '#0f0f12',
                borderRadius: '8px',
                padding: '12px',
                border: '1px solid #27272a',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px'
              }}>
                {/* macOS styled window controls */}
                <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', paddingBottom: '6px', borderBottom: '1px solid #1f1f23' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ef4444', display: 'inline-block' }} />
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#f59e0b', display: 'inline-block' }} />
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block' }} />
                </div>
                
                <div style={{
                  fontFamily: 'Consolas, Monaco, "Courier New", Courier, monospace',
                  fontSize: '0.78rem',
                  color: '#e0e0e0',
                  maxHeight: '160px',
                  overflowY: 'auto',
                  lineHeight: '1.5',
                  paddingRight: '6px'
                }}>
                  {details.logs.map((log: string, idx: number) => (
                    <div key={idx} style={{
                      color: log.toLowerCase().includes('error') ? '#f87171' : 
                             log.toLowerCase().includes('completed') ? '#34d399' : '#e0e0e0',
                      borderLeft: '2px solid',
                      borderLeftColor: log.toLowerCase().includes('error') ? '#ef4444' :
                                       log.toLowerCase().includes('completed') ? '#10b981' : 'transparent',
                      paddingLeft: log.toLowerCase().includes('error') || log.toLowerCase().includes('completed') ? '6px' : '0',
                      marginBottom: '2px'
                    }}>
                      <span style={{ color: '#71717a', marginRight: '8px' }}>[{idx + 1}]</span>
                      {log}
                    </div>
                  ))}
                  <div ref={logEndRef} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
