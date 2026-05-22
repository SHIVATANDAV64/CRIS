import type { Session, Model, Paper, DateGroup, WikiStats, Entity, Note, SearchResult, Decomposition, CrossDomainConnection } from './types'

const API = '/api'

// ── Sessions ──
export async function listSessions(limit = 50, offset = 0): Promise<Session[]> {
  const resp = await fetch(`${API}/sessions?limit=${limit}&offset=${offset}`)
  const data = await resp.json()
  return data.sessions || []
}

export async function createSession(title = 'New Chat'): Promise<Session> {
  const resp = await fetch(`${API}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  return resp.json()
}

export async function getSession(sessionId: string) {
  const resp = await fetch(`${API}/sessions/${sessionId}`)
  return resp.json()
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${API}/sessions/${sessionId}`, { method: 'DELETE' })
}

export async function updateSessionTitle(sessionId: string, title: string): Promise<void> {
  await fetch(`${API}/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export async function exportSession(sessionId: string) {
  const resp = await fetch(`${API}/sessions/${sessionId}/export`)
  const data = await resp.json()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `cris-session-${sessionId.slice(0, 8)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Models ──
export async function listModels(): Promise<Model[]> {
  const resp = await fetch(`${API}/models`)
  const data = await resp.json()
  return data.models || []
}

// ── Settings ──
export async function getSettings() {
  const resp = await fetch(`${API}/settings`)
  return resp.json()
}

export async function updateSettings(updates: Record<string, unknown>) {
  const resp = await fetch(`${API}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updates }),
  })
  return resp.json()
}

export async function resetSettings() {
  const resp = await fetch(`${API}/settings/reset`, { method: 'POST' })
  return resp.json()
}

// ── Chat (SSE streaming) ──
export function streamChat(
  message: string,
  sessionId: string | null,
  modelId: string,
  sourcePapers: string[] | null = null,
  webSearch: boolean | undefined = undefined,
  useReasoning: boolean = true,
  onSources: (sources: unknown[], sid: string) => void,
  onThinking: (content: string) => void,
  onContent: (content: string) => void,
  onDone: (sid: string) => void,
  onError: (error: string) => void,
  onStatus?: (status: string, message: string) => void,
  onDecomposition?: (decomp: Decomposition) => void,
): AbortController {
  const controller = new AbortController()

  fetch(`${API}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: controller.signal,
    body: JSON.stringify({
      message,
      use_reasoning: useReasoning,
      web_search: webSearch === true ? true : undefined,
      session_id: sessionId,
      source_papers: sourcePapers,
      model_id: modelId,
    }),
  }).then(async (resp) => {
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

    const reader = resp.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const dataStr = line.slice(6)
        if (dataStr === '[DONE]') continue

        try {
          const data = JSON.parse(dataStr)
          if (data.type === 'sources') {
            onSources(data.sources || [], data.session_id || '')
          } else if (data.type === 'thinking') {
            onThinking(data.content)
          } else if (data.type === 'content') {
            onContent(data.content)
          } else if (data.type === 'token') {
            onContent(data.token)
          } else if (data.type === 'done') {
            onDone(data.session_id || '')
          } else if (data.type === 'error') {
            onError(data.content || 'Unknown error')
          } else if (data.type === 'status' && onStatus) {
            onStatus(data.status || '', data.message || '')
          } else if (data.type === 'decomposition' && onDecomposition) {
            onDecomposition(data.decomposition)
          }
        } catch {
          // skip malformed SSE data
        }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      onError(err.message)
    }
  })

  return controller
}

// ── Papers / Sources ──
export async function listRawSources(): Promise<{ count: number; date_groups: DateGroup[] }> {
  const resp = await fetch(`${API}/raw-sources`)
  return resp.json()
}

export async function getPaper(arxivId: string): Promise<Paper> {
  const resp = await fetch(`${API}/raw-sources/${encodeURIComponent(arxivId)}`)
  return resp.json()
}

export async function migrateSources() {
  const resp = await fetch(`${API}/raw-sources/migrate`, { method: 'POST' })
  return resp.json()
}

// ── Wiki / Memory ──
export async function getWikiStats(): Promise<WikiStats> {
  const resp = await fetch(`${API}/wiki/stats`)
  return resp.json()
}

export async function getEntities(): Promise<{ count: number; entities: Entity[] }> {
  const resp = await fetch(`${API}/wiki/entities`)
  return resp.json()
}

export async function getNotes(): Promise<{ count: number; notes: Note[] }> {
  const resp = await fetch(`${API}/wiki/notes`)
  return resp.json()
}

export async function rebuildWiki() {
  const resp = await fetch(`${API}/wiki/rebuild`, { method: 'POST' })
  return resp.json()
}

// ── Web Search ──
export async function webSearch(query: string, numResults = 5): Promise<SearchResult[]> {
  const resp = await fetch(`${API}/web/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, num_results: numResults }),
  })
  const data = await resp.json()
  return data.results || []
}

export async function scrapeUrl(url: string) {
  const resp = await fetch(`${API}/web/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  return resp.json()
}

// ── Graph & Details ──
export async function getWikiGraph() {
  const resp = await fetch(`${API}/wiki/graph`)
  return resp.json()
}

export async function getWikiDetail(nodeType: string, nodeId: string) {
  const resp = await fetch(`${API}/wiki/detail/${nodeType}/${encodeURIComponent(nodeId)}`)
  return resp.json()
}

// ── Background Script Run Controls ──
export async function runIngestScript(params: {
  date?: string
  days_back?: number
  categories?: string
  max_papers?: number
  domain_mode?: boolean
  auto_compile?: boolean
}) {
  const resp = await fetch(`${API}/scripts/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return resp.json()
}

export interface IngestStatusDetails {
  running: boolean
  current_date: string | null
  dates_total: number
  dates_processed: number
  papers_fetched: number
  logs: string[]
  error: string | null
  progress_percent?: number
}

export async function getIngestStatus(): Promise<IngestStatusDetails> {
  const resp = await fetch(`${API}/scripts/ingest/status`)
  return resp.json()
}

export async function stopIngestScript() {
  const resp = await fetch(`${API}/scripts/ingest/stop`, { method: 'POST' })
  return resp.json()
}

export async function clearIngestStatus() {
  const resp = await fetch(`${API}/scripts/ingest/clear`, { method: 'POST' })
  return resp.json()
}

export async function runMigrateScript() {
  const resp = await fetch(`${API}/scripts/migrate`, { method: 'POST' })
  return resp.json()
}

export async function getMigrateStatus(): Promise<{ running: boolean }> {
  const resp = await fetch(`${API}/scripts/migrate/status`)
  return resp.json()
}

export interface ScriptStatusDetails {
  running: boolean
  logs: string[]
  error: string | null
}

export async function runCompileScript(rebuildWiki = true) {
  const resp = await fetch(`${API}/scripts/compile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rebuild_wiki: rebuildWiki })
  })
  return resp.json()
}

export async function getCompileStatus(): Promise<ScriptStatusDetails> {
  const resp = await fetch(`${API}/scripts/compile/status`)
  return resp.json()
}

export async function stopCompileScript() {
  const resp = await fetch(`${API}/scripts/compile/stop`, { method: 'POST' })
  return resp.json()
}

export async function clearCompileStatus() {
  const resp = await fetch(`${API}/scripts/compile/clear`, { method: 'POST' })
  return resp.json()
}

export async function runIndexScript(rebuild = true) {
  const resp = await fetch(`${API}/scripts/index`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rebuild: rebuild })
  })
  return resp.json()
}

export async function getIndexStatus(): Promise<ScriptStatusDetails> {
  const resp = await fetch(`${API}/scripts/index/status`)
  return resp.json()
}

export async function clearIndexStatus() {
  const resp = await fetch(`${API}/scripts/index/clear`, { method: 'POST' })
  return resp.json()
}

export async function discoverCrossDomainConnections(
  arxivId: string,
  sourceDomain: string,
  targetDomains: string[],
  topK = 5
): Promise<{ connections: CrossDomainConnection[]; indexing_occurred: boolean }> {
  const resp = await fetch(`${API}/research/cross-domain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      arxiv_id: arxivId,
      source_domain: sourceDomain,
      target_domains: targetDomains,
      top_k: topK,
    }),
  })
  if (!resp.ok) {
    throw new Error(`Failed to discover connections: ${resp.statusText}`)
  }
  return resp.json()
}

