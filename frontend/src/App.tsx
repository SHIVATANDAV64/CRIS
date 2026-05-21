import { useState, useEffect, useCallback } from 'react'
import { Sidebar } from './components/Sidebar'
import { ChatPanel } from './components/ChatPanel'
import { HistoryDashboard } from './components/HistoryDashboard'
import { WikiGraph } from './components/WikiGraph'
import { SettingsPanel } from './components/SettingsPanel'
import { SourcesBrowser } from './components/SourcesBrowser'
import { IngestionPanel } from './components/IngestionPanel'
import { streamChat, listSessions, listModels, getSettings, getIngestStatus } from './api'
import type { Message, Session, Model } from './types'

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [sidebarTab, setSidebarTab] = useState(() => {
    return localStorage.getItem('cris_active_tab') || 'chat'
  })
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedModel, setSelectedModel] = useState('darwin-opus')
  const [availableModels, setAvailableModels] = useState<Model[]>([])
  const [modelName, setModelName] = useState('CRIS Model')
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('cris_theme') as 'dark' | 'light') || 'dark'
  })
  const [droppedPapers, setDroppedPapers] = useState<Map<string, { id: string; title: string }>>(new Map())
  const [searchStatus, setSearchStatus] = useState<string>('')
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean>(false)
  const [reasoningEnabled, setReasoningEnabled] = useState<boolean>(true)
  const [isIngesting, setIsIngesting] = useState(false)

  // Ingestion status polling
  useEffect(() => {
    async function checkIngestion() {
      try {
        const res = await getIngestStatus()
        setIsIngesting(res.running)
      } catch {
        // silent
      }
    }
    checkIngestion()
    const timer = setInterval(checkIngestion, 4000)
    return () => clearInterval(timer)
  }, [])

  // Persist sidebar active tab
  useEffect(() => {
    localStorage.setItem('cris_active_tab', sidebarTab)
  }, [sidebarTab])

  // Theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('cris_theme', theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark')
  }, [])

  // Init
  useEffect(() => {
    loadSessions()
    loadModels()
    loadModelName()
  }, [])

  async function loadSessions() {
    try {
      const s = await listSessions()
      setSessions(s)
    } catch {
      // silent
    }
  }

  async function loadModels() {
    try {
      const models = await listModels()
      setAvailableModels(models)
      const saved = localStorage.getItem('cris_selected_model')
      if (saved && models.find(m => m.id === saved)) {
        setSelectedModel(saved)
      }
    } catch {
      // silent
    }
  }

  async function loadModelName() {
    try {
      const data = await getSettings()
      setModelName(data.config?.model?.modal_model || 'CRIS Model')
    } catch {
      // silent
    }
  }

  function selectModel(modelId: string) {
    setSelectedModel(modelId)
    localStorage.setItem('cris_selected_model', modelId)
  }

  async function createNewChat() {
    try {
      const resp = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Chat' }),
      })
      const session = await resp.json()
      setSessionId(session.id)
      setMessages([])
      setDroppedPapers(new Map())
      loadSessions()
      setSidebarTab('chat') // Switch active panel to Chat
    } catch {
      // silent
    }
  }

  async function loadSession(id: string) {
    setSessionId(id)
    try {
      const resp = await fetch(`/api/sessions/${id}`)
      const data = await resp.json()
      const msgs: Message[] = data.messages.map((m: any, i: number) => ({
        id: `msg-${i}`,
        role: m.role,
        content: m.content,
        thinking: m.thinking || '',
        sources: m.sources || [],
        timestamp: Date.now(),
      }))
      setMessages(msgs)
      loadSessions()
    } catch {
      // silent
    }
  }

  async function deleteSessionFn(id: string) {
    try {
      await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
      if (sessionId === id) {
        setSessionId(null)
        setMessages([])
      }
      loadSessions()
    } catch {
      // silent
    }
  }

  function sendMessage(message: string) {
    const sourcePaperIds = droppedPapers.size > 0 ? Array.from(droppedPapers.keys()) : null

    const userMsg: Message = {
      id: `msg-${Date.now()}-user`,
      role: 'user',
      content: message,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])
    setDroppedPapers(new Map())

    const assistantId = `msg-${Date.now()}-assistant`
    let fullContent = ''
    let fullThinking = ''

    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant',
      content: '',
      thinking: '',
      sources: [],
      timestamp: Date.now(),
    }])
    setSearchStatus('')

    streamChat(
      message,
      sessionId,
      selectedModel,
      sourcePaperIds,
      webSearchEnabled ? true : undefined,
      reasoningEnabled,
      (sources, sid) => {
        if (sid) setSessionId(sid)
        setSearchStatus('')
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, sources: sources as any } : m
        ))
      },
      (thinking) => {
        fullThinking += thinking
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, thinking: fullThinking } : m
        ))
      },
      (content) => {
        fullContent += content
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: fullContent } : m
        ))
      },
      (sid) => {
        if (sid) setSessionId(sid)
        setSearchStatus('')
        loadSessions()
      },
      (error) => {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content || `**Error**: ${error}` } : m
        ))
        setSearchStatus('')
      },
      (status, statusMessage) => {
        if (status === 'searching_web') {
          setSearchStatus(statusMessage || 'Searching the web...')
        } else if (status === 'web_results') {
          setSearchStatus(statusMessage || 'Web results found')
          setTimeout(() => setSearchStatus(''), 2000)
        } else if (status === 'decomposing') {
          setSearchStatus(statusMessage || 'Decomposing research query...')
        }
      },
      (decomp) => {
        setSearchStatus('')
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, decomposition: decomp } : m
        ))
      }
    )
  }

  function handlePaperDrop(arxivId: string, title: string) {
    setDroppedPapers(prev => {
      const next = new Map(prev)
      next.set(arxivId, { id: arxivId, title })
      return next
    })
  }

  function handlePaperRemove(arxivId: string) {
    setDroppedPapers(prev => {
      const next = new Map(prev)
      next.delete(arxivId)
      return next
    })
  }

  function exportCurrentSession() {
    if (sessionId) {
      fetch(`/api/sessions/${sessionId}/export`)
        .then(r => r.json())
        .then(data => {
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `cris-session-${sessionId.slice(0, 8)}.json`
          a.click()
          URL.revokeObjectURL(url)
        })
    }
  }

  // Keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.ctrlKey && e.key === 'n') {
        e.preventDefault()
        createNewChat()
      }
      if (e.ctrlKey && e.key === 'e') {
        e.preventDefault()
        exportCurrentSession()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [sessionId])

  const renderActiveTabContent = () => {
    switch (sidebarTab) {
      case 'chat':
        return (
          <ChatPanel
            messages={messages}
            onSend={sendMessage}
            droppedPapers={droppedPapers}
            onPaperDrop={handlePaperDrop}
            onPaperRemove={handlePaperRemove}
            onToggleSidebar={() => {}}
            searchStatus={searchStatus}
            webSearchEnabled={webSearchEnabled}
            onToggleWebSearch={() => setWebSearchEnabled(prev => !prev)}
            reasoningEnabled={reasoningEnabled}
            onToggleReasoning={() => setReasoningEnabled(prev => !prev)}
            theme={theme}
          />
        )
      case 'library':
        return (
          <SourcesBrowser
            activeReferences={droppedPapers}
            onAddReferences={(papers) => {
              setDroppedPapers(prev => {
                const next = new Map(prev)
                papers.forEach(p => {
                  next.set(p.id, { id: p.id, title: p.title })
                })
                return next
              })
              setSidebarTab('chat')
            }}
          />
        )
      case 'history':
        return (
          <HistoryDashboard
            sessions={sessions}
            onSessionSelect={(id) => {
              loadSession(id)
              setSidebarTab('chat')
            }}
            onDeleteSession={deleteSessionFn}
          />
        )
      case 'wiki':
        return <WikiGraph />
      case 'ingestion':
        return <IngestionPanel />
      case 'settings':
        return <SettingsPanel />
      default:
        return (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
            Select a view from the sidebar
          </div>
        )
    }
  }

  return (
    <div className="app-container" style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      <Sidebar
        currentTab={sidebarTab}
        onTabChange={setSidebarTab}
        onNewChat={createNewChat}
        selectedModel={selectedModel}
        availableModels={availableModels}
        onSelectModel={selectModel}
        onToggleTheme={toggleTheme}
        theme={theme}
        onPaperDrop={handlePaperDrop}
        isIngesting={isIngesting}
      />
      {renderActiveTabContent()}
    </div>
  )
}

export default App
