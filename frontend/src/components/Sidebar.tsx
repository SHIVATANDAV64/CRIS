import { useState, useRef, useEffect } from 'react'
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
  onPaperDrop?: (id: string, title: string) => void
  isIngesting?: boolean
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
  onPaperDrop,
  isIngesting = false,
}: SidebarProps) {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const [chatDragOver, setChatDragOver] = useState(false)
  const [expanded, setExpanded] = useState<boolean>(() => {
    const saved = localStorage.getItem('cris_sidebar_expanded')
    return saved === 'true'
  })
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    localStorage.setItem('cris_sidebar_expanded', String(expanded))
  }, [expanded])

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setModelDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const currentModel = availableModels.find(m => m.id === selectedModel)

  const TABS = [
    { key: 'chat', label: 'Chat', icon: <ChatIcon /> },
    { key: 'ingestion', label: 'Ingest arXiv', icon: <DownloadIcon /> },
    { key: 'library', label: 'Library', icon: <LibraryIcon /> },
    { key: 'history', label: 'History', icon: <ClockIcon /> },
    { key: 'wiki', label: 'Wiki Graph', icon: <WikiIcon /> },
    { key: 'settings', label: 'Settings', icon: <SettingsIcon /> },
  ]

  return (
    <aside className={`sidebar ${expanded ? '' : 'thin-sidebar'}`}>
      <div className="sidebar-header">
        <div className="logo" title="CRIS - Research Intelligence">
          <div className="logo-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="6" />
              <circle cx="12" cy="12" r="2" fill="currentColor" />
            </svg>
          </div>
          <div className="logo-text">
            <h1>CRIS</h1>
            <div className="logo-subtitle">Research Intelligence</div>
          </div>
        </div>

        <div className="new-chat-btn-wrapper">
          <button 
            className="new-chat-btn" 
            onClick={onNewChat} 
            title="New Chat"
          >
            <div className="new-chat-btn-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </div>
            <span className="new-chat-btn-text">New Chat</span>
          </button>
        </div>
      </div>

      <nav className="sidebar-nav">
        {TABS.map(tab => {
          const isChat = tab.key === 'chat'
          const isIngestion = tab.key === 'ingestion'
          return (
            <button
              key={tab.key}
              className={`nav-tab-button ${currentTab === tab.key ? 'active' : ''} ${isChat && chatDragOver ? 'drag-over' : ''}`}
              onClick={() => onTabChange(tab.key)}
              title={expanded ? undefined : tab.label}
              onDragOver={isChat ? (e) => {
                if (e.dataTransfer.types.includes('application/cris-paper')) {
                  e.preventDefault()
                  e.dataTransfer.dropEffect = 'copy'
                  setChatDragOver(true)
                }
              } : undefined}
              onDragLeave={isChat ? () => setChatDragOver(false) : undefined}
              onDrop={isChat ? (e) => {
                e.preventDefault()
                setChatDragOver(false)
                const paperData = e.dataTransfer.getData('application/cris-paper')
                if (paperData) {
                  try {
                    const { arxiv_id, title } = JSON.parse(paperData)
                    if (onPaperDrop) {
                      onPaperDrop(arxiv_id, title)
                    }
                    onTabChange('chat')
                  } catch {
                    // invalid
                  }
                }
              } : undefined}
            >
              <div className="nav-tab-icon-box" style={{ position: 'relative' }}>
                {tab.icon}
                {isIngestion && isIngesting && (
                  <span 
                    style={{
                      position: 'absolute',
                      top: '-2px',
                      right: '-2px',
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--accent-blue)',
                      border: '1px solid var(--bg-primary)',
                      animation: 'pulse 1.5s infinite alternate'
                    }} 
                  />
                )}
              </div>
              <span className="nav-tab-text" style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                <span style={{ flex: 1, textAlign: 'left' }}>{tab.label}</span>
                {isIngestion && isIngesting && expanded && (
                  <span 
                    style={{
                      fontSize: '0.62rem',
                      fontWeight: 600,
                      color: '#ffffff',
                      backgroundColor: 'var(--accent-blue)',
                      padding: '2px 6px',
                      borderRadius: '10px',
                      lineHeight: '1',
                      marginLeft: '6px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px'
                    }}
                  >
                    Active
                  </span>
                )}
              </span>
              {!expanded && <span className="tooltip">{tab.label}</span>}
            </button>
          )
        })}
      </nav>

      <div className="sidebar-footer">
        {/* Model Selection Dropdown */}
        <div className="model-selector-wrapper" ref={dropdownRef}>
          <button 
            className="model-selector-btn-new" 
            onClick={() => setModelDropdownOpen(v => !v)}
            title={`Active Model: ${currentModel?.name || selectedModel}`}
          >
            <div className="model-selector-icon-box">
              <span className={`model-status-dot ${selectedModel === 'darwin-opus' ? 'opus' : 'emerald'}`} />
            </div>
            <span className="model-selector-text">
              {currentModel?.name || selectedModel}
            </span>
          </button>
          
          {modelDropdownOpen && (
            <div className="model-dropdown-new">
              <div className="model-dropdown-header-new">Model Selection</div>
              <div className="model-dropdown-list-new">
                {availableModels.map(m => (
                  <div
                    key={m.id}
                    className={`model-dropdown-item-new ${m.id === selectedModel ? 'active' : ''}`}
                    onClick={() => { onSelectModel(m.id); setModelDropdownOpen(false) }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                      <div className="model-dropdown-item-name-new">{m.name}</div>
                      <span className="model-dropdown-item-provider-new">{m.provider}</span>
                    </div>
                    <div className="model-dropdown-item-desc-new">{m.description}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Theme Toggle */}
        <div className="theme-toggle-wrapper">
          <button 
            className="theme-toggle-btn-new" 
            onClick={onToggleTheme} 
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
          >
            <div className="theme-toggle-icon-box">
              {theme === 'dark' ? '☀' : '☾'}
            </div>
            <span className="theme-toggle-text">
              {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
            </span>
          </button>
        </div>

        {/* Collapse Toggle Button */}
        <div style={{ width: '100%', display: 'flex', justifyContent: 'center', margin: '4px 0 8px 0' }}>
          <button 
            className="collapse-toggle-btn"
            onClick={() => setExpanded(prev => !prev)}
            title={expanded ? "Collapse Sidebar" : "Expand Sidebar"}
          >
            <svg 
              width="14" 
              height="14" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2.5" 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              className="collapse-toggle-icon"
            >
              <polyline points="11 17 6 12 11 7" />
              <polyline points="18 17 13 12 18 7" />
            </svg>
          </button>
        </div>
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

function DownloadIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
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

function LibraryIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  )
}
