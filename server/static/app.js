// CRIS Chat Interface v2.0 — Client-side logic with session management, domain browsing, settings, memory, and web search

const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

// State
let sessionId = null;
let currentTab = 'history';
let selectedPapers = new Set();
let droppedPapers = new Map(); // arxiv_id -> {title, id}
let webSearchVisible = false;
let selectedModel = 'darwin-opus';
let availableModels = [];

// ── Initialization ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    loadModelName();
    loadModels();
    loadSelectedModel();
});

async function loadModelName() {
    try {
        const resp = await fetch('/api/settings');
        const data = await resp.json();
        const model = data.config?.model?.modal_model || 'CRIS Model';
        document.getElementById('model-name').textContent = model;
    } catch (e) {
        console.error('Failed to load model name:', e);
    }
}

async function loadModels() {
    try {
        const resp = await fetch('/api/models');
        const data = await resp.json();
        availableModels = data.models;
        renderModelDropdown();
    } catch (e) {
        console.error('Failed to load models:', e);
    }
}

function loadSelectedModel() {
    const saved = localStorage.getItem('cris_selected_model');
    if (saved && availableModels.find(m => m.id === saved)) {
        selectedModel = saved;
    }
    updateModelSelectorDisplay();
}

function renderModelDropdown() {
    const list = document.getElementById('model-dropdown-list');
    if (!list || availableModels.length === 0) return;

    list.innerHTML = availableModels.map(m => `
        <div class="model-dropdown-item ${m.id === selectedModel ? 'active' : ''}" onclick="selectModel('${m.id}')">
            <div class="model-dropdown-item-info">
                <div class="model-dropdown-item-name">${escapeHtml(m.name)}</div>
                <div class="model-dropdown-item-desc">${escapeHtml(m.description)}</div>
            </div>
            <span class="model-dropdown-item-provider">${m.provider}</span>
        </div>
    `).join('');
}

function toggleModelDropdown() {
    const dropdown = document.getElementById('model-dropdown');
    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
}

function selectModel(modelId) {
    selectedModel = modelId;
    localStorage.setItem('cris_selected_model', modelId);
    updateModelSelectorDisplay();
    renderModelDropdown();
    document.getElementById('model-dropdown').style.display = 'none';
}

function updateModelSelectorDisplay() {
    const nameEl = document.getElementById('model-selector-name');
    const model = availableModels.find(m => m.id === selectedModel);
    if (nameEl && model) {
        nameEl.textContent = model.name;
    }
}

document.addEventListener('click', (e) => {
    const selector = document.getElementById('model-selector');
    const dropdown = document.getElementById('model-dropdown');
    if (selector && dropdown && !selector.contains(e.target)) {
        dropdown.style.display = 'none';
    }
});

// ── Tab Navigation ─────────────────────────────────────────────────────
function switchTab(tab) {
    currentTab = tab;

    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

    document.querySelectorAll('.sidebar-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');

    if (tab === 'history') loadHistory();
    if (tab === 'memory') loadMemory();
    if (tab === 'sources') loadRawSources();
    if (tab === 'settings') loadSettings();
}

// ── Session / History Management ────────────────────────────────────────
async function loadHistory() {
    const container = document.getElementById('history-list');
    container.innerHTML = '<div class="loading-placeholder">Loading conversations...</div>';

    try {
        const resp = await fetch('/api/sessions');
        const data = await resp.json();

        if (data.sessions.length === 0) {
            container.innerHTML = '<div class="empty-state">No conversations yet. Start a new chat!</div>';
            return;
        }

        container.innerHTML = data.sessions.map(s => `
            <div class="history-item ${s.id === sessionId ? 'active' : ''}" onclick="loadSession('${s.id}')">
                <div class="history-item-content">
                    <div class="history-item-title">${escapeHtml(s.title)}</div>
                    <div class="history-item-meta">${formatDate(s.updated_at)} • ${s.message_count} messages</div>
                </div>
                <button class="history-delete-btn" onclick="event.stopPropagation(); deleteSession('${s.id}')" title="Delete">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                        <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>
                    </svg>
                </button>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = '<div class="error-state">Failed to load history</div>';
        console.error(e);
    }
}

async function createNewChat() {
    try {
        const resp = await fetch('/api/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: 'New Chat' }),
        });
        const session = await resp.json();
        sessionId = session.id;

        chatMessages.innerHTML = `
            <div class="message system-message">
                <div class="message-content">
                    <div class="welcome-card">
                        <h2>New Conversation</h2>
                        <p>Ask a cross-domain research question to begin.</p>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('chat-title').textContent = 'New Chat';
        document.getElementById('chat-subtitle').textContent = 'Start a new research conversation';

        if (window.innerWidth <= 768) {
            document.getElementById('sidebar').classList.remove('visible');
            document.getElementById('sidebar').classList.add('hidden');
        }

        loadHistory();
        chatInput.focus();
    } catch (e) {
        console.error('Failed to create new chat:', e);
    }
}

async function loadSession(sessionIdToLoad) {
    sessionId = sessionIdToLoad;

    try {
        const resp = await fetch(`/api/sessions/${sessionId}`);
        const data = await resp.json();

        document.getElementById('chat-title').textContent = data.session.title;
        document.getElementById('chat-subtitle').textContent = `${data.messages.length} messages`;

        chatMessages.innerHTML = '';
        for (const msg of data.messages) {
            if (msg.role === 'user') {
                addMessage('user', msg.content);
            } else if (msg.role === 'assistant') {
                addAssistantMessage(msg.content, msg.thinking, msg.sources);
            }
        }

        scrollToBottom();
        loadHistory();

        if (window.innerWidth <= 768) {
            document.getElementById('sidebar').classList.remove('visible');
            document.getElementById('sidebar').classList.add('hidden');
        }
    } catch (e) {
        console.error('Failed to load session:', e);
    }
}

async function deleteSession(sessionIdToDelete) {
    if (!confirm('Delete this conversation?')) return;

    try {
        await fetch(`/api/sessions/${sessionIdToDelete}`, { method: 'DELETE' });

        if (sessionId === sessionIdToDelete) {
            sessionId = null;
            chatMessages.innerHTML = `
                <div class="message system-message">
                    <div class="message-content">
                        <div class="welcome-card">
                            <h2>Welcome to CRIS</h2>
                            <p>I'm your cross-domain research intelligence assistant.</p>
                        </div>
                    </div>
                </div>
            `;
            document.getElementById('chat-title').textContent = 'Cross-Domain Research Assistant';
            document.getElementById('chat-subtitle').textContent = 'Powered by wiki-style knowledge synthesis';
        }

        loadHistory();
    } catch (e) {
        console.error('Failed to delete session:', e);
    }
}

// ── Memory Panel ────────────────────────────────────────────────────────
async function loadMemory() {
    const statsContainer = document.getElementById('memory-stats');
    const entityContainer = document.getElementById('entity-list');
    const noteContainer = document.getElementById('note-list');

    statsContainer.innerHTML = '<div class="loading-placeholder">Loading memory...</div>';
    entityContainer.innerHTML = '';
    noteContainer.innerHTML = '';

    try {
        // Load stats
        const statsResp = await fetch('/api/wiki/stats');
        const stats = await statsResp.json();

        statsContainer.innerHTML = `
            <div class="memory-stat">
                <div class="memory-stat-value">${stats.sources}</div>
                <div class="memory-stat-label">Sources</div>
            </div>
            <div class="memory-stat">
                <div class="memory-stat-value">${stats.concepts}</div>
                <div class="memory-stat-label">Concepts</div>
            </div>
            <div class="memory-stat">
                <div class="memory-stat-value">${stats.entities}</div>
                <div class="memory-stat-label">Entities</div>
            </div>
            <div class="memory-stat">
                <div class="memory-stat-value">${stats.notes}</div>
                <div class="memory-stat-label">Notes</div>
            </div>
        `;

        // Load entities
        const entitiesResp = await fetch('/api/wiki/entities');
        const entities = await entitiesResp.json();

        if (entities.entities.length === 0) {
            entityContainer.innerHTML = '<div class="empty-state">No entities extracted yet. Start a conversation!</div>';
        } else {
            entityContainer.innerHTML = entities.entities.map(e => `
                <div class="entity-item">
                    <span class="entity-type ${e.type}">${e.type}</span>
                    <span class="entity-name">${escapeHtml(e.name)}</span>
                    <span class="entity-mentions">${e.mentions} mentions</span>
                </div>
            `).join('');
        }

        // Load notes
        const notesResp = await fetch('/api/wiki/notes');
        const notes = await notesResp.json();

        if (notes.notes.length === 0) {
            noteContainer.innerHTML = '<div class="empty-state">No conversation notes yet.</div>';
        } else {
            noteContainer.innerHTML = notes.notes.map(n => `
                <div class="note-item">
                    <div class="note-title">${escapeHtml(n.title)}</div>
                    <div class="note-date">${formatDate(n.date)}</div>
                </div>
            `).join('');
        }
    } catch (e) {
        statsContainer.innerHTML = '<div class="error-state">Failed to load memory</div>';
        console.error(e);
    }
}

async function rebuildWiki() {
    if (!confirm('Rebuild wiki summaries and graph? This may take a moment.')) return;

    try {
        const resp = await fetch('/api/wiki/rebuild', { method: 'POST' });
        const result = await resp.json();
        if (result.status === 'success') {
            alert('Wiki rebuilt successfully!');
            loadMemory();
        }
    } catch (e) {
        alert('Failed to rebuild wiki');
        console.error(e);
    }
}

// ── Web Search ──────────────────────────────────────────────────────────
function toggleWebSearch() {
    webSearchVisible = !webSearchVisible;
    const panel = document.getElementById('web-search-panel');
    panel.style.display = webSearchVisible ? 'block' : 'none';
    if (webSearchVisible) {
        document.getElementById('web-search-input').focus();
    }
}

async function performWebSearch() {
    const input = document.getElementById('web-search-input');
    const resultsContainer = document.getElementById('web-search-results');
    const query = input.value.trim();

    if (!query) return;

    resultsContainer.innerHTML = '<div class="loading-placeholder">Searching...</div>';

    try {
        const resp = await fetch('/api/web/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, num_results: 5 }),
        });
        const data = await resp.json();

        if (data.results.length === 0) {
            resultsContainer.innerHTML = '<div class="empty-state">No results found. Web search may not be configured.</div>';
            return;
        }

        resultsContainer.innerHTML = data.results.map(r => `
            <div class="web-search-result" onclick="scrapeUrl('${r.url}')">
                <div class="web-search-result-title">${escapeHtml(r.title)}</div>
                <div class="web-search-result-url">${escapeHtml(r.url)}</div>
                <div class="web-search-result-snippet">${escapeHtml(r.snippet || '').substring(0, 150)}...</div>
            </div>
        `).join('');
    } catch (e) {
        resultsContainer.innerHTML = '<div class="error-state">Search failed</div>';
        console.error(e);
    }
}

async function scrapeUrl(url) {
    const resultsContainer = document.getElementById('web-search-results');
    resultsContainer.innerHTML = '<div class="loading-placeholder">Scraping page...</div>';

    try {
        const resp = await fetch('/api/web/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        const data = await resp.json();

        if (data.status === 'success') {
            resultsContainer.innerHTML = `
                <div class="web-search-result">
                    <div class="web-search-result-title">${escapeHtml(data.title)}</div>
                    <div class="web-search-result-url">${escapeHtml(data.url)}</div>
                    <div class="web-search-result-snippet">${escapeHtml(data.content).substring(0, 500)}...</div>
                </div>
            `;
        } else {
            resultsContainer.innerHTML = `<div class="error-state">Failed to scrape: ${data.error}</div>`;
        }
    } catch (e) {
        resultsContainer.innerHTML = '<div class="error-state">Scrape failed</div>';
        console.error(e);
    }
}

// ── Raw Sources Browsing ────────────────────────────────────────────────
async function loadRawSources() {
    const container = document.getElementById('sources-browser');
    container.innerHTML = '<div class="loading-placeholder">Loading papers...</div>';

    try {
        const resp = await fetch('/api/raw-sources');
        const data = await resp.json();

        if (!data.date_groups || data.date_groups.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    No papers ingested yet.
                    <p style="font-size: 0.75rem; color: var(--text-tertiary); margin-top: 8px;">
                        Run: <code>python scripts/ingest_arxiv.py --days-back 1</code>
                    </p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="sources-header">
                <span class="sources-count">${data.count} papers</span>
                <button class="send-selected-btn" onclick="sendSelectedToChat()" id="send-selected-btn" style="display: none;">
                    Send Selected (${selectedPapers.size}) to Chat
                </button>
            </div>
        ` + data.date_groups.map(dg => `
            <div class="date-group">
                <div class="date-group-header" onclick="toggleDateGroup('${dg.date}')">
                    <div class="date-group-info">
                        <span class="date-group-icon"></span>
                        <div>
                            <div class="date-group-title">${dg.date}</div>
                            <div class="date-group-subtitle">${dg.paper_count} papers • ${dg.categories.length} categories</div>
                        </div>
                    </div>
                    <svg class="expand-icon" id="date-icon-${dg.date}" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>
                    </svg>
                </div>
                <div class="date-group-content" id="date-content-${dg.date}" style="display: none;">
                    ${dg.categories.map(cat => `
                        <div class="category-group">
                            <div class="category-header">
                                <span class="category-icon">${getDomainIcon(cat.category)}</span>
                                <span class="category-name">${escapeHtml(cat.display_name)}</span>
                                <span class="category-count">${cat.paper_count}</span>
                            </div>
                            <div class="papers-list">
                                ${cat.papers.map(p => `
                                    <div class="paper-item" id="paper-item-${p.arxiv_id}" draggable="true" ondragstart="onPaperDragStart(event, '${p.arxiv_id}', '${escapeHtml(p.title).replace(/'/g, "\\'")}')" ondragend="onPaperDragEnd(event)">
                                        <div class="drag-handle">
                                            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                                                <circle cx="4" cy="3" r="1.2"/>
                                                <circle cx="10" cy="3" r="1.2"/>
                                                <circle cx="4" cy="7" r="1.2"/>
                                                <circle cx="10" cy="7" r="1.2"/>
                                                <circle cx="4" cy="11" r="1.2"/>
                                                <circle cx="10" cy="11" r="1.2"/>
                                            </svg>
                                        </div>
                                        <div class="paper-checkbox" onclick="togglePaperSelection('${p.arxiv_id}')">
                                            <input type="checkbox" id="cb-${p.arxiv_id}" ${selectedPapers.has(p.arxiv_id) ? 'checked' : ''}>
                                        </div>
                                        <div class="paper-item-content" onclick="openRawPaperDetail('${p.arxiv_id}')">
                                            <div class="paper-item-title">${escapeHtml(p.title)}</div>
                                            <div class="paper-item-meta">
                                                <span class="paper-item-id">${p.arxiv_id}</span>
                                                <span class="paper-item-authors">${escapeHtml((p.authors || []).slice(0, 2).join(', '))}${(p.authors || []).length > 2 ? ' et al.' : ''}</span>
                                            </div>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');

        updateSendButton();
    } catch (e) {
        container.innerHTML = '<div class="error-state">Failed to load papers</div>';
        console.error(e);
    }
}

function toggleDateGroup(date) {
    const content = document.getElementById(`date-content-${date}`);
    const icon = document.getElementById(`date-icon-${date}`);
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.classList.add('rotated');
    } else {
        content.style.display = 'none';
        icon.classList.remove('rotated');
    }
}

function togglePaperSelection(arxivId) {
    if (selectedPapers.has(arxivId)) {
        selectedPapers.delete(arxivId);
    } else {
        selectedPapers.add(arxivId);
    }

    const cb = document.getElementById(`cb-${arxivId}`);
    if (cb) cb.checked = selectedPapers.has(arxivId);

    updateSendButton();
}

function updateSendButton() {
    const btn = document.getElementById('send-selected-btn');
    if (btn) {
        btn.style.display = selectedPapers.size > 0 ? 'flex' : 'none';
        btn.textContent = `Send Selected (${selectedPapers.size}) to Chat`;
    }
}

async function sendSelectedToChat() {
    if (selectedPapers.size === 0) return;

    const sourcePapers = Array.from(selectedPapers);

    // Create new session or use current
    if (!sessionId) {
        const resp = await fetch('/api/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: `Analysis: ${sourcePapers.length} papers` }),
        });
        const session = await resp.json();
        sessionId = session.id;
    }

    // Clear chat and show loading
    chatMessages.innerHTML = '';
    addMessage('user', `Analyze these ${sourcePapers.length} papers and find cross-domain connections.`);

    const loadingId = addLoading();
    sendBtn.disabled = true;

    try {
        const resp = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: `Analyze these ${sourcePapers.length} papers and find cross-domain connections.`,
                use_reasoning: true,
                session_id: sessionId,
                source_papers: sourcePapers,
                model_id: selectedModel,
            }),
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        removeLoading(loadingId);

        const assistantDiv = document.createElement('div');
        assistantDiv.className = 'message assistant-message';
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        const labelDiv = document.createElement('div');
        labelDiv.className = 'message-label';
        labelDiv.textContent = 'CRIS';
        const thinkingDiv = document.createElement('div');
        thinkingDiv.className = 'thinking-section';
        thinkingDiv.style.display = 'none';
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.innerHTML = '<div class="thinking-indicator"><span class="thinking-icon">✦</span> Thinking...</div>';
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'sources-section';
        sourcesDiv.style.display = 'none';

        messageContent.appendChild(labelDiv);
        messageContent.appendChild(thinkingDiv);
        messageContent.appendChild(textDiv);
        messageContent.appendChild(sourcesDiv);
        assistantDiv.appendChild(messageContent);
        chatMessages.appendChild(assistantDiv);
        scrollToBottom();

        let contentStarted = false;

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullContent = '';
        let fullThinking = '';
        let thinkingStarted = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const dataStr = line.slice(6);
                if (dataStr === '[DONE]') continue;

                try {
                    const data = JSON.parse(dataStr);

                    if (data.type === 'sources') {
                        sessionId = data.session_id || sessionId;
                        if (data.sources && data.sources.length > 0) {
                            const chips = data.sources.map(s => {
                                const typeClass = s.contribution_type || '';
                                const typeLabel = s.contribution_type ?
                                    `<span class="source-type ${typeClass}">${s.contribution_type}</span>` : '';
                                return `<span class="source-chip">${typeLabel} ${s.arxiv_id}</span>`;
                            }).join('');
                            sourcesDiv.innerHTML = `
                                <div class="sources-title">Sources (${data.sources.length} papers)</div>
                                ${chips}
                            `;
                            sourcesDiv.style.display = 'block';
                        }
                    } else if (data.type === 'thinking') {
                        fullThinking = data.content;
                        if (!thinkingStarted) {
                            thinkingStarted = true;
                            const thinkId = 'think-' + Date.now();
                            thinkingDiv.innerHTML = `
                                <button class="thinking-toggle expanded" onclick="toggleThinking('${thinkId}', this)">
                                    <span class="arrow">▼</span>
                                    <span>Reasoning trace</span>
                                </button>
                                <div class="thinking-content visible" id="${thinkId}">${escapeHtml(fullThinking)}</div>
                            `;
                            thinkingDiv.style.display = 'block';
                        } else {
                            const thinkContent = thinkingDiv.querySelector('.thinking-content');
                            if (thinkContent) {
                                thinkContent.textContent = fullThinking;
                                thinkContent.scrollTop = thinkContent.scrollHeight;
                            }
                        }
                        scrollToBottom();
                    } else if (data.type === 'content') {
                        if (!contentStarted) {
                            contentStarted = true;
                            textDiv.innerHTML = '';
                        }
                        fullContent += data.content;
                        textDiv.innerHTML = formatMarkdown(fullContent);
                        scrollToBottom();
                    } else if (data.type === 'done') {
                        sessionId = data.session_id || sessionId;
                        loadHistory();
                    }
                } catch (e) {
                    console.error('Error parsing SSE data:', e);
                }
            }
        }
    } catch (e) {
        removeLoading(loadingId);
        addMessage('assistant', 'Connection error. Is the server running?');
        console.error(e);
    } finally {
        sendBtn.disabled = false;
    }
}

async function openRawPaperDetail(arxivId) {
    const modal = document.getElementById('paper-modal');
    const titleEl = document.getElementById('paper-modal-title');
    const bodyEl = document.getElementById('paper-modal-body');

    modal.classList.add('visible');
    titleEl.textContent = 'Loading...';
    bodyEl.innerHTML = '<div class="loading-placeholder">Loading paper details...</div>';

    try {
        const resp = await fetch(`/api/raw-sources/${encodeURIComponent(arxivId)}`);
        const paper = await resp.json();

        titleEl.textContent = paper.title;
        bodyEl.innerHTML = `
            <div class="paper-detail-section">
                <div class="paper-detail-label">arXiv ID</div>
                <div class="paper-detail-value">${paper.arxiv_id}</div>
            </div>
            <div class="paper-detail-section">
                <div class="paper-detail-label">Authors</div>
                <div class="paper-detail-value">${(paper.authors || []).join(', ')}</div>
            </div>
            <div class="paper-detail-section">
                <div class="paper-detail-label">Categories</div>
                <div class="paper-detail-value">${paper.categories || 'N/A'}</div>
            </div>
            <div class="paper-detail-section">
                <div class="paper-detail-label">Published</div>
                <div class="paper-detail-value">${paper.created || 'N/A'}</div>
            </div>
            <div class="paper-detail-section">
                <div class="paper-detail-label">Abstract</div>
                <div class="paper-detail-value paper-abstract-full">${escapeHtml(paper.abstract || '')}</div>
            </div>
            <div class="paper-detail-section">
                <div class="paper-detail-label">Fetched At</div>
                <div class="paper-detail-value">${paper.fetched_at || 'N/A'}</div>
            </div>
        `;
    } catch (e) {
        bodyEl.innerHTML = '<div class="error-state">Failed to load paper details</div>';
        console.error(e);
    }
}

function closePaperModal() {
    document.getElementById('paper-modal').classList.remove('visible');
}

// ── Settings Panel ─────────────────────────────────────────────────────
async function loadSettings() {
    const container = document.getElementById('settings-panel');
    container.innerHTML = '<div class="loading-placeholder">Loading settings...</div>';

    try {
        const resp = await fetch('/api/settings');
        const data = await resp.json();
        const config = data.config;

        container.innerHTML = `
            <div class="settings-section">
                <h4>arXiv Configuration</h4>
                <div class="setting-item">
                    <label>OAI URL</label>
                    <input type="text" id="setting-arxiv-url" value="${config.arxiv.oai_url}" data-path="arxiv.oai_url">
                </div>
                <div class="setting-item">
                    <label>Rate Limit (seconds)</label>
                    <input type="number" id="setting-rate-limit" value="${config.arxiv.rate_limit_seconds}" data-path="arxiv.rate_limit_seconds" min="1" max="60">
                </div>
                <div class="setting-item">
                    <label>Categories (comma-separated)</label>
                    <input type="text" id="setting-categories" value="${config.arxiv.categories.join(', ')}" data-path="arxiv.categories" data-type="array">
                </div>
                <div class="setting-item">
                    <label>Max Papers per Fetch</label>
                    <input type="number" id="setting-max-papers" value="${config.arxiv.max_papers_per_fetch}" data-path="arxiv.max_papers_per_fetch" min="1">
                </div>
            </div>

            <div class="settings-section">
                <h4>Model Configuration</h4>
                <div class="setting-item">
                    <label>API URL</label>
                    <input type="text" id="setting-modal-url" value="${config.model.modal_api_url}" data-path="model.modal_api_url">
                </div>
                <div class="setting-item">
                    <label>Model Name</label>
                    <input type="text" id="setting-model-name" value="${config.model.modal_model}" data-path="model.modal_model">
                </div>
                <div class="setting-item">
                    <label>Max Tokens</label>
                    <input type="number" id="setting-max-tokens" value="${config.model.max_tokens}" data-path="model.max_tokens" min="256" max="16384">
                </div>
                <div class="setting-item">
                    <label>Temperature</label>
                    <input type="number" id="setting-temperature" value="${config.model.temperature}" data-path="model.temperature" min="0" max="2" step="0.1">
                </div>
                <div class="setting-item">
                    <label>Top P</label>
                    <input type="number" id="setting-top-p" value="${config.model.top_p}" data-path="model.top_p" min="0" max="1" step="0.05">
                </div>
            </div>

            <div class="settings-section">
                <h4>Chat Configuration</h4>
                <div class="setting-item">
                    <label>Max History Messages</label>
                    <input type="number" id="setting-max-history" value="${config.chat.max_history_messages}" data-path="chat.max_history_messages" min="5" max="100">
                </div>
                <div class="setting-item">
                    <label>Context Exchanges</label>
                    <input type="number" id="setting-context-exchanges" value="${config.chat.context_exchanges}" data-path="chat.context_exchanges" min="1" max="10">
                </div>
                <div class="setting-item">
                    <label>Max Thinking Length</label>
                    <input type="number" id="setting-max-thinking" value="${config.chat.max_thinking_length}" data-path="chat.max_thinking_length" min="500" max="8000">
                </div>
            </div>

            <div class="settings-section">
                <h4>Search Configuration</h4>
                <div class="setting-item">
                    <label>Results Limit</label>
                    <input type="number" id="setting-search-limit" value="${config.search.results_limit}" data-path="search.results_limit" min="5" max="100">
                </div>
                <div class="setting-item">
                    <label>Context Entries Limit</label>
                    <input type="number" id="setting-context-limit" value="${config.search.context_entries_limit}" data-path="search.context_entries_limit" min="5" max="50">
                </div>
            </div>

            <div class="settings-actions">
                <button class="settings-btn primary" onclick="saveSettings()">Save Settings</button>
                <button class="settings-btn secondary" onclick="resetSettings()">Reset to Defaults</button>
            </div>
        `;
    } catch (e) {
        container.innerHTML = '<div class="error-state">Failed to load settings</div>';
        console.error(e);
    }
}

async function saveSettings() {
    const updates = {};

    document.querySelectorAll('#settings-panel input[data-path]').forEach(input => {
        const path = input.dataset.path.split('.');
        let obj = updates;
        for (let i = 0; i < path.length - 1; i++) {
            if (!obj[path[i]]) obj[path[i]] = {};
            obj = obj[path[i]];
        }

        const key = path[path.length - 1];
        if (input.dataset.type === 'array') {
            obj[key] = input.value.split(',').map(s => s.trim()).filter(Boolean);
        } else if (input.type === 'number') {
            obj[key] = parseFloat(input.value);
        } else {
            obj[key] = input.value;
        }
    });

    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ updates }),
        });
        alert('Settings saved successfully!');
        loadModelName();
    } catch (e) {
        alert('Failed to save settings');
        console.error(e);
    }
}

async function resetSettings() {
    if (!confirm('Reset all settings to defaults?')) return;

    try {
        await fetch('/api/settings/reset', { method: 'POST' });
        alert('Settings reset to defaults');
        loadSettings();
        loadModelName();
    } catch (e) {
        alert('Failed to reset settings');
        console.error(e);
    }
}

// ── Drag and Drop ──────────────────────────────────────────────────────
function onPaperDragStart(event, arxivId, title) {
    draggedPaper = { arxivId, title };
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData('text/plain', arxivId);
    event.target.style.opacity = '0.5';
}

function onPaperDragEnd(event) {
    event.target.style.opacity = '1';
    draggedPaper = null;
    document.getElementById('chat-input-area')?.classList.remove('drag-over');
}

function onChatDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    document.getElementById('chat-input-area')?.classList.add('drag-over');
}

function onChatDragLeave(event) {
    document.getElementById('chat-input-area')?.classList.remove('drag-over');
}

function onChatDrop(event) {
    event.preventDefault();
    document.getElementById('chat-input-area')?.classList.remove('drag-over');

    const arxivId = event.dataTransfer.getData('text/plain');
    if (!arxivId || droppedPapers.has(arxivId)) return;

    droppedPapers.set(arxivId, {
        id: arxivId,
        title: draggedPaper?.title || arxivId,
    });

    renderDroppedPapers();
}

function renderDroppedPapers() {
    const container = document.getElementById('dropped-papers');
    if (!container) return;

    if (droppedPapers.size === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'flex';
    container.innerHTML = Array.from(droppedPapers.entries()).map(([id, paper]) => `
        <span class="dropped-paper-chip">
            <span class="chip-id">${id}</span>
            <span class="chip-title">${escapeHtml(paper.title.substring(0, 40))}...</span>
            <button class="chip-remove" onclick="removeDroppedPaper('${id}')">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
                    <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>
                </svg>
            </button>
        </span>
    `).join('');
}

function removeDroppedPaper(arxivId) {
    droppedPapers.delete(arxivId);
    renderDroppedPapers();
}

function clearDroppedPapers() {
    droppedPapers.clear();
    renderDroppedPapers();
}
function setQuery(text) {
    chatInput.value = text;
    chatInput.focus();
    autoResize(chatInput);
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
}

async function sendMessage() {
    const message = chatInput.value.trim();
    if (!message) return;

    chatInput.value = '';
    autoResize(chatInput);

    addMessage('user', message);

    const loadingId = addLoading();
    sendBtn.disabled = true;

    const sourcePaperIds = droppedPapers.size > 0 ? Array.from(droppedPapers.keys()) : null;

    try {
        const resp = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                use_reasoning: true,
                session_id: sessionId,
                source_papers: sourcePaperIds,
                model_id: selectedModel,
            }),
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        removeLoading(loadingId);

        const assistantDiv = document.createElement('div');
        assistantDiv.className = 'message assistant-message';
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        const labelDiv = document.createElement('div');
        labelDiv.className = 'message-label';
        labelDiv.textContent = 'CRIS';
        const thinkingDiv = document.createElement('div');
        thinkingDiv.className = 'thinking-section';
        thinkingDiv.style.display = 'none';
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.innerHTML = '<div class="thinking-indicator"><span class="thinking-icon">✦</span> Thinking...</div>';
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'sources-section';
        sourcesDiv.style.display = 'none';

        messageContent.appendChild(labelDiv);
        messageContent.appendChild(thinkingDiv);
        messageContent.appendChild(textDiv);
        messageContent.appendChild(sourcesDiv);
        assistantDiv.appendChild(messageContent);
        chatMessages.appendChild(assistantDiv);
        scrollToBottom();

        let contentStarted = false;

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullContent = '';
        let fullThinking = '';
        let thinkingStarted = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const dataStr = line.slice(6);
                if (dataStr === '[DONE]') continue;

                try {
                    const data = JSON.parse(dataStr);

                    if (data.type === 'sources') {
                        sessionId = data.session_id || sessionId;
                        if (data.sources && data.sources.length > 0) {
                            const chips = data.sources.map(s => {
                                const typeClass = s.contribution_type || '';
                                const typeLabel = s.contribution_type ?
                                    `<span class="source-type ${typeClass}">${s.contribution_type}</span>` : '';
                                return `<span class="source-chip">${typeLabel} ${s.arxiv_id}</span>`;
                            }).join('');
                            sourcesDiv.innerHTML = `
                                <div class="sources-title">Sources (${data.sources.length} papers)</div>
                                ${chips}
                            `;
                            sourcesDiv.style.display = 'block';
                        }
                    } else if (data.type === 'thinking') {
                        fullThinking = data.content;
                        if (!thinkingStarted) {
                            thinkingStarted = true;
                            const thinkId = 'think-' + Date.now();
                            thinkingDiv.innerHTML = `
                                <button class="thinking-toggle expanded" onclick="toggleThinking('${thinkId}', this)">
                                    <span class="arrow">▼</span>
                                    <span>Reasoning trace</span>
                                </button>
                                <div class="thinking-content visible" id="${thinkId}">${escapeHtml(fullThinking)}</div>
                            `;
                            thinkingDiv.style.display = 'block';
                        } else {
                            const thinkContent = thinkingDiv.querySelector('.thinking-content');
                            if (thinkContent) {
                                thinkContent.textContent = fullThinking;
                                thinkContent.scrollTop = thinkContent.scrollHeight;
                            }
                        }
                        scrollToBottom();
                    } else if (data.type === 'content') {
                        if (!contentStarted) {
                            contentStarted = true;
                            textDiv.innerHTML = '';
                        }
                        fullContent += data.content;
                        textDiv.innerHTML = formatMarkdown(fullContent);
                        scrollToBottom();
                    } else if (data.type === 'done') {
                        sessionId = data.session_id || sessionId;
                        loadHistory();
                    }
                } catch (e) {
                    console.error('Error parsing SSE data:', e);
                }
            }
        }
    } catch (e) {
        removeLoading(loadingId);
        addMessage('assistant', 'Connection error. Is the server running?');
        console.error(e);
    } finally {
        sendBtn.disabled = false;
        clearDroppedPapers();
    }
}

// ── DOM Helpers ─────────────────────────────────────────────────────────
function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = `message ${role}-message`;

    const labelText = role === 'user' ? 'You' : 'CRIS';
    div.innerHTML = `
        <div class="message-content">
            <div class="message-label">${labelText}</div>
            <div class="message-text">${formatMarkdown(text)}</div>
        </div>
    `;

    chatMessages.appendChild(div);
    scrollToBottom();
}

function addAssistantMessage(content, thinking = '', sources = []) {
    const div = document.createElement('div');
    div.className = 'message assistant-message';

    let thinkingHtml = '';
    if (thinking) {
        const thinkId = 'think-' + Date.now();
        thinkingHtml = `
            <div class="thinking-section" style="display: block;">
                <button class="thinking-toggle" onclick="toggleThinking('${thinkId}', this)">
                    <span class="arrow">▶</span>
                    <span>Reasoning trace</span>
                </button>
                <div class="thinking-content" id="${thinkId}">${escapeHtml(thinking)}</div>
            </div>
        `;
    }

    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        const chips = sources.map(s => {
            const typeClass = s.contribution_type || '';
            const typeLabel = s.contribution_type ?
                `<span class="source-type ${typeClass}">${s.contribution_type}</span>` : '';
            return `<span class="source-chip">${typeLabel} ${s.arxiv_id}</span>`;
        }).join('');
        sourcesHtml = `
            <div class="sources-section" style="display: block;">
                <div class="sources-title">Sources (${sources.length} papers)</div>
                ${chips}
            </div>
        `;
    }

    div.innerHTML = `
        <div class="message-content">
            <div class="message-label">CRIS</div>
            ${thinkingHtml}
            <div class="message-text">${formatMarkdown(content)}</div>
            ${sourcesHtml}
        </div>
    `;

    chatMessages.appendChild(div);
}

function addLoading() {
    const id = 'loading-' + Date.now();
    const div = document.createElement('div');
    div.className = 'message assistant-message';
    div.id = id;
    div.innerHTML = `
        <div class="message-content">
            <div class="message-label">CRIS</div>
            <div class="loading-dots">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    chatMessages.appendChild(div);
    scrollToBottom();
    return id;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('visible');
    sidebar.classList.toggle('hidden');
}

function toggleThinking(id, btn) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.toggle('visible');
        btn.classList.toggle('expanded');
    }
}

// ── Utility Functions ──────────────────────────────────────────────────
function escapeHtml(text) {
    if (!text) return '';
    const el = document.createElement('div');
    el.textContent = text;
    return el.innerHTML;
}

function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function getDomainIcon(domain) {
    const icons = {
        'cs.AI': '🤖',
        'cs.CL': '💬',
        'cs.LG': '',
        'q-bio.BM': '🧬',
        'cs.CV': '👁️',
        'cs.RO': '🦾',
        'cs.SE': '💻',
        'cs.CR': '🔒',
        'cs.DB': '🗄️',
        'cs.IR': '🔍',
        'cs.NE': '🧠',
        'cs.HC': '🖱️',
        'stat.ML': '📈',
        'q-bio.QM': '🔬',
        'physics.data-an': '⚛️',
        'math.ST': '📐',
    };
    return icons[domain] || '📄';
}

function formatMarkdown(text) {
    if (!text) return '';
    if (text.length > 50000) return escapeHtml(text.substring(0, 50000)) + '... (truncated)';
    let html = escapeHtml(text);
    html = html.replace(/\*\*([^\*]+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^\*]+?)\*/g, '<em>$1</em>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.split('\n\n').map(p => `<p>${p}</p>`).join('');
    html = html.replace(/\n/g, '<br>');
    html = html.replace(/<p>- (.+?)<\/p>/g, '<li>$1</li>');
    return html;
}
