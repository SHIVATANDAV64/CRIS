import { useState, useEffect, useRef } from 'react'
import { HistoryList } from './HistoryList'
import { MemoryPanel } from './MemoryPanel'
import { SourcesBrowser } from './SourcesBrowser'
import { SettingsPanel } from './SettingsPanel'
import type { Session, Model } from '../types'

interface SidebarProps {
  visible: boolean
  currentTab: string
  onTabChange: (tab: string) => void
  sessions: Session[]
  onSessionSelect: (id: string) => void
  onNewChat: () => void
  onDeleteSession: (id: string) => void
  activeSessionId: string | null
  selectedModel: string
  availableModels: Model[]
  onSelectModel: (id: string) => void
  modelName: string
  onToggleTheme: () => void
  theme: 'dark' | 'light'
}

const TABS = [
  { key: 'history', label: 'History', icon: <ClockIcon /> },
  { key: 'memory', label: 'Memory', icon: <MemoryIcon /> },
  { key: 'sources', label: 'Sources', icon: <GridIcon /> },
  { key: 'settings', label: 'Settings', icon: <SettingsIcon /> },
]

export function Sidebar({
  visible, currentTab, onTabChange, sessions, onSessionSelect,
  onNewChat, onDeleteSession, activeSessionId, selectedModel,
  availableModels, onSelectModel, modelName, onToggleTheme, theme,
}: SidebarProps) {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setModelDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const currentModel = availableModels.find(m => m.id === selectedModel)

  return (
    <aside className={`sidebar ${visible ? '' : 'hidden'}`}>
      <div className="sidebar-header">
        <div className="logo">
          <div className="logo-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="6" />
              <circle cx="12" cy="12" r="2" fill="currentColor" />
            </svg>
          </div>
          <div className="logo-text">
            <h1>CRIS</h1>
            <span className="logo-subtitle">Research Intelligence</span>
          </div>
        </div>
        <button className="new-chat-btn" onClick={onNewChat}>
          <svg width="14" height="14" viewBox="0 0 18 18" fill="currentColor">
            <path d="M9 3v12M3 9h12" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
          </svg>
          New Chat
        </button>
      </div>

      <nav className="sidebar-nav">
        {TABS.map(tab => (
          <button
            key={tab.key}
            className={`nav-tab ${currentTab === tab.key ? 'active' : ''}`}
            onClick={() => onTabChange(tab.key)}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </nav>

      <div className={`sidebar-content ${currentTab === 'history' ? 'active' : ''}`}>
        <HistoryList sessions={sessions} activeId={activeSessionId} onSelect={onSessionSelect} onDelete={onDeleteSession} />
      </div>
      <div className={`sidebar-content ${currentTab === 'memory' ? 'active' : ''}`}>
        <MemoryPanel />
      </div>
      <div className={`sidebar-content ${currentTab === 'sources' ? 'active' : ''}`}>
        <SourcesBrowser />
      </div>
      <div className={`sidebar-content ${currentTab === 'settings' ? 'active' : ''}`}>
        <SettingsPanel />
      </div>

      <div className="sidebar-footer">
        <div className="model-badge">
          <div className="badge-dot" />
          <span>{modelName}</span>
        </div>

        <div className="model-selector" ref={dropdownRef}>
          <button className="model-selector-btn" onClick={() => setModelDropdownOpen(v => !v)}>
            <span className="model-selector-left">
              <span className="model-selector-dot" />
              <span className="model-selector-name">{currentModel?.name || selectedModel}</span>
            </span>
            <svg width="10" height="10" viewBox="0 0 12 12" fill="currentColor" style={{ transform: modelDropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 120ms' }}>
              <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
            </svg>
          </button>
          {modelDropdownOpen && (
            <div className="model-dropdown">
              <div className="model-dropdown-header">Select Model</div>
              <div className="model-dropdown-list">
                {availableModels.map(m => (
                  <div
                    key={m.id}
                    className={`model-dropdown-item ${m.id === selectedModel ? 'active' : ''}`}
                    onClick={() => { onSelectModel(m.id); setModelDropdownOpen(false) }}
                  >
                    <div>
                      <div className="model-dropdown-item-name">{m.name}</div>
                      <div className="model-dropdown-item-desc">{m.description}</div>
                    </div>
                    <span className="model-dropdown-item-provider">{m.provider}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <button className="theme-toggle-btn" onClick={onToggleTheme}>
          {theme === 'dark' ? '☀ Light' : '☾ Dark'}
        </button>

        <p className="version-text">CRIS v3.0 • 2025-26</p>
      </div>
    </aside>
  )
}

function ClockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 18 18" fill="none">
      <circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth="1.5" />
      <path d="M9 5v4l2.5 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function MemoryIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 18 18" fill="none">
      <rect x="3" y="3" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M6 6h6M6 9h6M6 12h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function GridIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 18 18" fill="none">
      <rect x="2" y="2" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="10" y="2" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="2" y="10" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="10" y="10" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

function SettingsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 18 18" fill="none">
      <circle cx="9" cy="9" r="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.5 3.5l1.5 1.5M13 13l1.5 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}
