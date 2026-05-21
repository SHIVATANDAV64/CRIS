import { useState, useRef } from 'react'
import type { Model } from '../types'

interface SidebarProps {
  currentTab: string
  onTabChange: (tab: string) => void
  onNewChat: () => void
  selectedModel: string
  availableModels: Model[]
  onSelectModel: (id: string) => void
  onToggleTheme: () => void
  theme: 'dark' | 'light'
}

export function Sidebar({
  currentTab,
  onTabChange,
  onNewChat,
  selectedModel,
  availableModels,
  onSelectModel,
  onToggleTheme,
  theme,
}: SidebarProps) {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const currentModel = availableModels.find(m => m.id === selectedModel)

  const TABS = [
    { key: 'chat', label: 'Chat', icon: <ChatIcon /> },
    { key: 'history', label: 'History', icon: <ClockIcon /> },
    { key: 'wiki', label: 'Wiki Graph', icon: <WikiIcon /> },
    { key: 'settings', label: 'Settings', icon: <SettingsIcon /> },
  ]

  return (
    <aside className="sidebar thin-sidebar">
      <div className="sidebar-header thin-header">
        <div className="logo thin-logo" title="CRIS - Research Intelligence">
          <div className="logo-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="6" />
              <circle cx="12" cy="12" r="2" fill="currentColor" />
            </svg>
          </div>
        </div>
        <button className="new-chat-btn-circle" onClick={onNewChat} title="New Chat">
          <svg width="16" height="16" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M9 3v12M3 9h12" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <nav className="sidebar-nav thin-nav">
        {TABS.map(tab => (
          <button
            key={tab.key}
            className={`nav-tab thin-tab ${currentTab === tab.key ? 'active' : ''}`}
            onClick={() => onTabChange(tab.key)}
            title={tab.label}
          >
            {tab.icon}
            <span className="tooltip">{tab.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer thin-footer">
        {/* Model quick select indicator dot */}
        <div className="model-selector thin-model-selector" ref={dropdownRef}>
          <button 
            className="model-dot-btn" 
            onClick={() => setModelDropdownOpen(v => !v)}
            title={`Active Model: ${currentModel?.name || selectedModel}. Click to change.`}
          >
            <span className="model-status-dot" style={{ backgroundColor: selectedModel === 'darwin-opus' ? 'var(--accent-coral)' : 'var(--accent-emerald)' }} />
          </button>
          {modelDropdownOpen && (
            <div className="model-dropdown thin-dropdown">
              <div className="model-dropdown-header">Model Selection</div>
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

        <button className="theme-toggle-btn thin-theme-btn" onClick={onToggleTheme} title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}>
          {theme === 'dark' ? '☀' : '☾'}
        </button>
      </div>
    </aside>
  )
}

function ChatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function ClockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

function WikiIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 3a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3zM6 15a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3zm12 0a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3zM18 9l-6 6M6 9l6 6M18 9v6" />
    </svg>
  )
}

function SettingsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}
