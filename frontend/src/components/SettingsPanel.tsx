import { useState, useEffect, useRef } from 'react'
import { 
  getSettings, 
  updateSettings, 
  resetSettings, 
  runIngestScript, 
  getIngestStatus, 
  runMigrateScript, 
  getMigrateStatus,
  rebuildWiki
} from '../api'

export function SettingsPanel() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  
  // Script configuration parameters
  const [ingestDate, setIngestDate] = useState('')
  const [ingestDaysBack, setIngestDaysBack] = useState(0)
  const [ingestCategories, setIngestCategories] = useState('')
  const [ingestMaxPapers, setIngestMaxPapers] = useState<number | ''>('')
  const [ingestDomainMode, setIngestDomainMode] = useState(true)

  // Running status
  const [ingestRunning, setIngestRunning] = useState(false)
  const [migrateRunning, setMigrateRunning] = useState(false)
  const [rebuildRunning, setRebuildRunning] = useState(false)

  // Notification message
  const [notification, setNotification] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null)

  const pollingRef = useRef<any>(null)

  useEffect(() => {
    load()
    checkStatuses()

    // Poll background task statuses every 3 seconds
    pollingRef.current = setInterval(() => {
      checkStatuses()
    }, 3000)

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [])

  async function load() {
    setLoading(true)
    try {
      const data = await getSettings()
      setConfig(data.config)
      if (data.config?.arxiv?.categories) {
        setIngestCategories(data.config.arxiv.categories.join(', '))
      }
    } catch {
      showNotification('Failed to load settings', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function checkStatuses() {
    try {
      const ingest = await getIngestStatus()
      setIngestRunning(ingest.running)

      const migrate = await getMigrateStatus()
      setMigrateRunning(migrate.running)
    } catch (err) {
      console.error('Failed to poll background task statuses:', err)
    }
  }

  function showNotification(text: string, type: 'success' | 'error' | 'info') {
    setNotification({ text, type })
    setTimeout(() => {
      setNotification(null)
    }, 4000)
  }

  async function handleSave() {
    try {
      await updateSettings(config)
      showNotification('Settings saved successfully', 'success')
    } catch {
      showNotification('Failed to save settings', 'error')
    }
  }

  async function handleReset() {
    if (!confirm('Reset all settings to defaults?')) return
    try {
      await resetSettings()
      load()
      showNotification('Settings reset to defaults', 'success')
    } catch {
      showNotification('Failed to reset settings', 'error')
    }
  }

  // Scripts triggers
  async function handleRunIngest() {
    if (ingestRunning) return
    try {
      const params: any = {}
      if (ingestDate) params.date = ingestDate
      if (ingestDaysBack > 0) params.days_back = Number(ingestDaysBack)
      if (ingestCategories) {
        params.categories = ingestCategories.split(',').map(s => s.trim()).filter(Boolean).join(',')
      }
      if (ingestMaxPapers !== '') params.max_papers = Number(ingestMaxPapers)
      params.domain_mode = ingestDomainMode

      const resp = await runIngestScript(params)
      if (resp.status === 'started') {
        setIngestRunning(true)
        showNotification('arXiv ingestion script started in background', 'success')
      } else {
        showNotification(resp.message || 'Already running or failed to start', 'info')
      }
    } catch (err: any) {
      showNotification('Error starting arXiv ingestion script', 'error')
    }
  }

  async function handleRunMigrate() {
    if (migrateRunning) return
    try {
      const resp = await runMigrateScript()
      if (resp.status === 'started') {
        setMigrateRunning(true)
        showNotification('Storage migration script started in background', 'success')
      } else {
        showNotification(resp.message || 'Already running or failed to start', 'info')
      }
    } catch {
      showNotification('Error starting storage migration script', 'error')
    }
  }

  async function handleRebuildWiki() {
    if (rebuildRunning) return
    setRebuildRunning(true)
    showNotification('Rebuilding wiki knowledge base...', 'info')
    try {
      await rebuildWiki()
      showNotification('Wiki knowledge base rebuilt successfully!', 'success')
    } catch {
      showNotification('Failed to rebuild wiki knowledge base', 'error')
    } finally {
      setRebuildRunning(false)
    }
  }

  function updateValue(path: string, value: any) {
    setConfig((prev: any) => {
      const obj = { ...prev }
      const parts = path.split('.')
      let current = obj
      for (let i = 0; i < parts.length - 1; i++) {
        current = { ...current[parts[i]] }
        obj[parts[i]] = current
      }
      current[parts[parts.length - 1]] = value
      return obj
    })
  }

  if (loading) return (
    <div className="dashboard-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ color: 'var(--text-tertiary)' }}>Loading settings...</span>
    </div>
  )
  if (!config) return (
    <div className="dashboard-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ color: 'var(--text-danger)' }}>Failed to load settings</span>
    </div>
  )

  return (
    <div className="dashboard-container" style={{ position: 'relative' }}>
      
      {/* Toast Notification */}
      {notification && (
        <div 
          style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            padding: '12px 20px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: notification.type === 'success' ? 'rgba(16,185,129,0.92)' : notification.type === 'error' ? 'rgba(220,38,38,0.92)' : 'rgba(24,99,220,0.92)',
            color: '#fff',
            fontSize: '0.8rem',
            fontWeight: 500,
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
            zIndex: 9999,
            transition: 'all 0.2s ease',
            backdropFilter: 'blur(4px)',
            WebkitBackdropFilter: 'blur(4px)'
          }}
        >
          {notification.text}
        </div>
      )}

      <div className="dashboard-header">
        <h1>Configuration Panel</h1>
        <p>Modify local configuration parameters and trigger background synchronization scripts</p>
      </div>

      <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '24px', marginBottom: '32px' }}>
        
        {/* arXiv Settings */}
        <div className="settings-card" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: '20px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>arXiv Fetcher</h3>
          <SettingItem label="OAI Feed URL" value={config.arxiv?.oai_url || ''} onChange={v => updateValue('arxiv.oai_url', v)} />
          <SettingItem label="Rate Limit (seconds)" value={config.arxiv?.rate_limit_seconds || 3} type="number" onChange={v => updateValue('arxiv.rate_limit_seconds', Number(v))} />
          <SettingItem label="Categories" value={(config.arxiv?.categories || []).join(', ')} onChange={v => updateValue('arxiv.categories', v.split(',').map((s: string) => s.trim()).filter(Boolean))} />
          <SettingItem label="Max Papers per Fetch" value={config.arxiv?.max_papers_per_fetch || 10} type="number" onChange={v => updateValue('arxiv.max_papers_per_fetch', Number(v))} />
        </div>

        {/* Model Settings */}
        <div className="settings-card" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: '20px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>AI Reasoning Model</h3>
          <SettingItem label="API Endpoint URL" value={config.model?.modal_api_url || ''} onChange={v => updateValue('model.modal_api_url', v)} />
          <SettingItem label="Model Identifier" value={config.model?.modal_model || ''} onChange={v => updateValue('model.modal_model', v)} />
          <SettingItem label="Max Tokens" value={config.model?.max_tokens || 4096} type="number" onChange={v => updateValue('model.max_tokens', Number(v))} />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <SettingItem label="Temperature" value={config.model?.temperature || 0.7} type="number" step="0.1" onChange={v => updateValue('model.temperature', Number(v))} />
            <SettingItem label="Top P" value={config.model?.top_p || 0.9} type="number" step="0.05" onChange={v => updateValue('model.top_p', Number(v))} />
          </div>
        </div>

        {/* Chat Settings */}
        <div className="settings-card" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: '20px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>Chat Configuration</h3>
          <SettingItem label="Max Saved History Limit" value={config.chat?.max_history_messages || 20} type="number" onChange={v => updateValue('chat.max_history_messages', Number(v))} />
          <SettingItem label="Context Window (Exchanges)" value={config.chat?.context_exchanges || 5} type="number" onChange={v => updateValue('chat.context_exchanges', Number(v))} />
          <SettingItem label="Max Thinking Block Size" value={config.chat?.max_thinking_length || 4000} type="number" onChange={v => updateValue('chat.max_thinking_length', Number(v))} />
        </div>

        {/* Search Settings */}
        <div className="settings-card" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: '20px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '16px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>Search Configuration</h3>
          <SettingItem label="Search Results Limit" value={config.search?.results_limit || 20} type="number" onChange={v => updateValue('search.results_limit', Number(v))} />
          <SettingItem label="Context Entries Limit" value={config.search?.context_entries_limit || 10} type="number" onChange={v => updateValue('search.context_entries_limit', Number(v))} />
        </div>
      </div>

      <div className="settings-actions" style={{ display: 'flex', gap: '12px', marginBottom: '40px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '32px' }}>
        <button 
          onClick={handleSave}
          style={{
            background: 'var(--accent-coral)',
            color: '#fff',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            padding: '10px 20px',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'opacity 0.15s ease'
          }}
          onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
          onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
        >
          Save Settings
        </button>
        <button 
          onClick={handleReset}
          style={{
            background: 'var(--bg-secondary)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '10px 20px',
            fontSize: '0.85rem',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'background 0.15s ease'
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'var(--bg-secondary)'}
        >
          Reset to Defaults
        </button>
      </div>

      {/* Script Controller Section */}
      <div className="settings-header" style={{ marginBottom: '24px' }}>
        <h1>Automation Scripts Controller</h1>
        <p>Trigger background execution workflows directly without using the terminal</p>
      </div>

      <div className="scripts-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '24px', marginBottom: '40px' }}>
        
        {/* arXiv Ingestion Runner */}
        <div className="settings-card" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--text-primary)', margin: 0 }}>ArXiv Paper Ingestion</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem' }}>
              <span 
                style={{ 
                  display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', 
                  backgroundColor: ingestRunning ? 'var(--accent-emerald)' : 'var(--text-muted)',
                  animation: ingestRunning ? 'skeleton-pulse 1.2s infinite' : 'none' 
                }} 
              />
              <span style={{ color: ingestRunning ? 'var(--accent-emerald)' : 'var(--text-secondary)', fontWeight: 500 }}>
                {ingestRunning ? 'RUNNING' : 'IDLE'}
              </span>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 500, color: 'var(--text-secondary)' }}>Target Date</label>
              <input 
                type="text" 
                placeholder="YYYY-MM-DD" 
                value={ingestDate} 
                onChange={(e) => setIngestDate(e.target.value)} 
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '8px 12px', fontSize: '0.8rem', color: 'var(--text-primary)', outline: 'none' }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 500, color: 'var(--text-secondary)' }}>Days Back</label>
              <input 
                type="number" 
                value={ingestDaysBack} 
                onChange={(e) => setIngestDaysBack(Number(e.target.value))} 
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '8px 12px', fontSize: '0.8rem', color: 'var(--text-primary)', outline: 'none' }}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '12px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 500, color: 'var(--text-secondary)' }}>Categories</label>
              <input 
                type="text" 
                value={ingestCategories} 
                onChange={(e) => setIngestCategories(e.target.value)} 
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '8px 12px', fontSize: '0.8rem', color: 'var(--text-primary)', outline: 'none' }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 500, color: 'var(--text-secondary)' }}>Max Papers</label>
              <input 
                type="number" 
                placeholder="Unlimited" 
                value={ingestMaxPapers} 
                onChange={(e) => setIngestMaxPapers(e.target.value === '' ? '' : Number(e.target.value))} 
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '8px 12px', fontSize: '0.8rem', color: 'var(--text-primary)', outline: 'none' }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
            <input 
              type="checkbox" 
              id="domainMode" 
              checked={ingestDomainMode} 
              onChange={(e) => setIngestDomainMode(e.target.checked)} 
              style={{ cursor: 'pointer' }}
            />
            <label htmlFor="domainMode" style={{ fontSize: '0.75rem', fontWeight: 500, color: 'var(--text-secondary)', cursor: 'pointer' }}>
              Sort papers into domain folders
            </label>
          </div>

          <button 
            onClick={handleRunIngest}
            disabled={ingestRunning}
            style={{
              width: '100%',
              background: ingestRunning ? 'var(--bg-hover)' : 'var(--text-primary)',
              color: ingestRunning ? 'var(--text-tertiary)' : 'var(--bg-primary)',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              padding: '10px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: ingestRunning ? 'not-allowed' : 'pointer',
              marginTop: '8px',
              transition: 'opacity 0.15s ease'
            }}
            onMouseEnter={(e) => { if (!ingestRunning) e.currentTarget.style.opacity = '0.9' }}
            onMouseLeave={(e) => { if (!ingestRunning) e.currentTarget.style.opacity = '1' }}
          >
            {ingestRunning ? 'Ingestion In Progress...' : 'Run Ingestion Script'}
          </button>
        </div>

        {/* Storage Migration and Wiki compiler */}
        <div className="settings-card" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          {/* Storage Migration */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px', marginBottom: '12px' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--text-primary)', margin: 0 }}>Storage Migration</h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem' }}>
                <span 
                  style={{ 
                    display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', 
                    backgroundColor: migrateRunning ? 'var(--accent-emerald)' : 'var(--text-muted)',
                    animation: migrateRunning ? 'skeleton-pulse 1.2s infinite' : 'none' 
                  }} 
                />
                <span style={{ color: migrateRunning ? 'var(--accent-emerald)' : 'var(--text-secondary)', fontWeight: 500 }}>
                  {migrateRunning ? 'RUNNING' : 'IDLE'}
                </span>
              </div>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', lineHeight: '1.4', marginBottom: '12px' }}>
              Migrate raw PDF/JSON papers from legacy folders into the organized daily domain storage hierarchy.
            </p>
            <button 
              onClick={handleRunMigrate}
              disabled={migrateRunning}
              style={{
                width: '100%',
                background: migrateRunning ? 'var(--bg-hover)' : 'var(--bg-primary)',
                color: migrateRunning ? 'var(--text-tertiary)' : 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '8px',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: migrateRunning ? 'not-allowed' : 'pointer',
                transition: 'background 0.15s ease'
              }}
              onMouseEnter={(e) => { if (!migrateRunning) e.currentTarget.style.background = 'var(--bg-hover)' }}
              onMouseLeave={(e) => { if (!migrateRunning) e.currentTarget.style.background = 'var(--bg-primary)' }}
            >
              {migrateRunning ? 'Migrating...' : 'Run Storage Migration'}
            </button>
          </div>

          {/* Rebuild Wiki Graph */}
          <div style={{ marginTop: 'auto' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '10px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>Rebuild Wiki Graph</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', lineHeight: '1.4', marginBottom: '12px' }}>
              Re-parse all markdown notes, concepts, and links to rebuild the force-directed interactive graph layout.
            </p>
            <button 
              onClick={handleRebuildWiki}
              disabled={rebuildRunning}
              style={{
                width: '100%',
                background: rebuildRunning ? 'var(--bg-hover)' : 'var(--bg-primary)',
                color: rebuildRunning ? 'var(--text-tertiary)' : 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '8px',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: rebuildRunning ? 'not-allowed' : 'pointer',
                transition: 'background 0.15s ease'
              }}
              onMouseEnter={(e) => { if (!rebuildRunning) e.currentTarget.style.background = 'var(--bg-hover)' }}
              onMouseLeave={(e) => { if (!rebuildRunning) e.currentTarget.style.background = 'var(--bg-primary)' }}
            >
              {rebuildRunning ? 'Rebuilding Wiki...' : 'Rebuild Wiki Graph'}
            </button>
          </div>

        </div>
      </div>

    </div>
  )
}

function SettingItem({ 
  label, 
  value, 
  type = 'text', 
  step, 
  onChange 
}: { 
  label: string; 
  value: any; 
  type?: string; 
  step?: string; 
  onChange: (v: any) => void 
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
      <label style={{ fontSize: '0.78rem', fontWeight: 500, color: 'var(--text-secondary)' }}>{label}</label>
      <input 
        type={type} 
        value={value} 
        step={step} 
        onChange={e => onChange(e.target.value)} 
        style={{
          background: 'var(--bg-primary)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '8px 12px',
          fontSize: '0.82rem',
          color: 'var(--text-primary)',
          outline: 'none',
          transition: 'border-color var(--transition-fast)'
        }}
        onFocus={(e) => e.currentTarget.style.borderColor = 'var(--accent-coral)'}
        onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
      />
    </div>
  )
}
