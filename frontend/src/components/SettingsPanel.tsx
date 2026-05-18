import { useState, useEffect } from 'react'
import { getSettings, updateSettings, resetSettings } from '../api'

export function SettingsPanel() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const data = await getSettings()
      setConfig(data.config)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    try {
      await updateSettings(config)
      alert('Settings saved!')
    } catch {
      alert('Failed to save settings')
    }
  }

  async function handleReset() {
    if (!confirm('Reset all settings to defaults?')) return
    try {
      await resetSettings()
      load()
    } catch {
      alert('Failed to reset settings')
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

  if (loading) return <div className="settings-panel"><div className="loading-placeholder">Loading settings...</div></div>
  if (!config) return <div className="settings-panel"><div className="error-state">Failed to load settings</div></div>

  return (
    <div className="settings-panel">
      <div className="settings-section">
        <h4>arXiv Configuration</h4>
        <SettingItem label="OAI URL" value={config.arxiv?.oai_url || ''} onChange={v => updateValue('arxiv.oai_url', v)} />
        <SettingItem label="Rate Limit (seconds)" value={config.arxiv?.rate_limit_seconds || 3} type="number" onChange={v => updateValue('arxiv.rate_limit_seconds', Number(v))} />
        <SettingItem label="Categories" value={(config.arxiv?.categories || []).join(', ')} onChange={v => updateValue('arxiv.categories', v.split(',').map((s: string) => s.trim()).filter(Boolean))} />
        <SettingItem label="Max Papers per Fetch" value={config.arxiv?.max_papers_per_fetch || 10} type="number" onChange={v => updateValue('arxiv.max_papers_per_fetch', Number(v))} />
      </div>

      <div className="settings-section">
        <h4>Model Configuration</h4>
        <SettingItem label="API URL" value={config.model?.modal_api_url || ''} onChange={v => updateValue('model.modal_api_url', v)} />
        <SettingItem label="Model Name" value={config.model?.modal_model || ''} onChange={v => updateValue('model.modal_model', v)} />
        <SettingItem label="Max Tokens" value={config.model?.max_tokens || 4096} type="number" onChange={v => updateValue('model.max_tokens', Number(v))} />
        <SettingItem label="Temperature" value={config.model?.temperature || 0.7} type="number" step="0.1" onChange={v => updateValue('model.temperature', Number(v))} />
        <SettingItem label="Top P" value={config.model?.top_p || 0.9} type="number" step="0.05" onChange={v => updateValue('model.top_p', Number(v))} />
      </div>

      <div className="settings-section">
        <h4>Chat Configuration</h4>
        <SettingItem label="Max History Messages" value={config.chat?.max_history_messages || 20} type="number" onChange={v => updateValue('chat.max_history_messages', Number(v))} />
        <SettingItem label="Context Exchanges" value={config.chat?.context_exchanges || 5} type="number" onChange={v => updateValue('chat.context_exchanges', Number(v))} />
        <SettingItem label="Max Thinking Length" value={config.chat?.max_thinking_length || 4000} type="number" onChange={v => updateValue('chat.max_thinking_length', Number(v))} />
      </div>

      <div className="settings-section">
        <h4>Search Configuration</h4>
        <SettingItem label="Results Limit" value={config.search?.results_limit || 20} type="number" onChange={v => updateValue('search.results_limit', Number(v))} />
        <SettingItem label="Context Entries Limit" value={config.search?.context_entries_limit || 10} type="number" onChange={v => updateValue('search.context_entries_limit', Number(v))} />
      </div>

      <div className="settings-actions">
        <button className="settings-btn primary" onClick={handleSave}>Save Settings</button>
        <button className="settings-btn secondary" onClick={handleReset}>Reset to Defaults</button>
      </div>
    </div>
  )
}

function SettingItem({ label, value, type = 'text', step, onChange }: { label: string; value: any; type?: string; step?: string; onChange: (v: any) => void }) {
  return (
    <div className="setting-item">
      <label>{label}</label>
      <input type={type} value={value} step={step} onChange={e => onChange(e.target.value)} />
    </div>
  )
}
