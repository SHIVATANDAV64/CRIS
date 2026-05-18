import { useState, useEffect, useCallback } from 'react'
import { Sidebar } from './components/Sidebar'
import { ChatPanel } from './components/ChatPanel'
import { streamChat, listSessions, listModels, getSettings } from './api'
import type { Message, Session, Model } from './types'

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [sidebarTab, setSidebarTab] = useState('history')
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedModel, setSelectedModel] = useState('darwin-opus')
  const [availableModels, setAvailableModels] = useState<Model[]>([])
  const [modelName, setModelName] = useState('CRIS Model')
  const [sidebarVisible, setSidebarVisible] = useState(window.innerWidth > 768)
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('cris_theme') as 'dark' | 'light') || 'dark'
  })
  const [droppedPapers, setDroppedPapers] = useState<Map<string, { id: string; title: string }>>(new Map())

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

    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant',
      content: '',
      thinking: '',
      sources: [],
      timestamp: Date.now(),
    }])

    streamChat(
      message,
      sessionId,
      selectedModel,
      sourcePaperIds,
      (sources, sid) => {
        if (sid) setSessionId(sid)
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, sources: sources as any } : m
        ))
      },
      (thinking) => {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, thinking } : m
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
        loadSessions()
      },
      (error) => {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content || `**Error**: ${error}` } : m
        ))
      },
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

  return (
    <div className="app-container">
      <Sidebar
        visible={sidebarVisible}
        currentTab={sidebarTab}
        onTabChange={setSidebarTab}
        sessions={sessions}
        onSessionSelect={loadSession}
        onNewChat={createNewChat}
        onDeleteSession={deleteSessionFn}
        activeSessionId={sessionId}
        selectedModel={selectedModel}
        availableModels={availableModels}
        onSelectModel={selectModel}
        modelName={modelName}
        onToggleTheme={toggleTheme}
        theme={theme}
      />
      <ChatPanel
        messages={messages}
        onSend={sendMessage}
        droppedPapers={droppedPapers}
        onPaperDrop={handlePaperDrop}
        onPaperRemove={handlePaperRemove}
        onToggleSidebar={() => setSidebarVisible(v => !v)}
      />
    </div>
  )
}

export default App
