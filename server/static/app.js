// CRIS Chat Interface — Client-side logic with conversation memory and streaming

const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

// Session ID for conversation continuity
let sessionId = null;

// ─ Load stats on page load ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
});

async function loadStats() {
    try {
        const resp = await fetch('/api/stats');
        const stats = await resp.json();
        document.getElementById('stat-papers').textContent = stats.total_papers || 0;

        const types = stats.contribution_types || {};
        document.getElementById('stat-types').textContent = Object.keys(types).length || '—';

        // Count unique domains (rough estimate from types)
        document.getElementById('stat-domains').textContent =
            stats.total_papers > 0 ? '4' : '—';
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

// ── Message handling ────────────────────────────────────────────────────
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

    // Clear input
    chatInput.value = '';
    autoResize(chatInput);

    // Add user message
    addMessage('user', message);

    // Show loading
    const loadingId = addLoading();

    // Disable send
    sendBtn.disabled = true;

    try {
        const resp = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                use_reasoning: true,
                session_id: sessionId,
            }),
        });

        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }

        removeLoading(loadingId);

        // Create assistant message container for streaming
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

        // Process streaming response
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
                            const paperSources = data.sources.filter(s => !s.arxiv_id.startsWith('concept:'));
                            if (paperSources.length > 0) {
                                const chips = paperSources.map(s => {
                                    const typeClass = s.contribution_type || '';
                                    const typeLabel = s.contribution_type ?
                                        `<span class="source-type ${typeClass}">${s.contribution_type}</span>` : '';
                                    return `<span class="source-chip">${typeLabel} ${s.arxiv_id}</span>`;
                                }).join('');
                                sourcesDiv.innerHTML = `
                                    <div class="sources-title">Sources (${paperSources.length} papers)</div>
                                    ${chips}
                                `;
                                sourcesDiv.style.display = 'block';
                            }
                        }
                    } else if (data.type === 'thinking') {
                        // Model outputs cumulative thinking, so replace content
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
                            // Update existing thinking content (cumulative)
                            const thinkContent = thinkingDiv.querySelector('.thinking-content');
                            if (thinkContent) {
                                thinkContent.textContent = fullThinking;
                                thinkContent.scrollTop = thinkContent.scrollHeight;
                            }
                        }
                        scrollToBottom();
                    } else if (data.type === 'content') {
                        // Model outputs cumulative content, so replace
                        fullContent = data.content;
                        textDiv.innerHTML = formatMarkdown(fullContent);
                        scrollToBottom();
                    } else if (data.type === 'done') {
                        sessionId = data.session_id || sessionId;
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

// ── DOM helpers ──────────────────────────────────────────────────────────
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

function escapeHtml(text) {
    const el = document.createElement('div');
    el.textContent = text;
    return el.innerHTML;
}

// ─ Simple markdown formatting ──────────────────────────────────────────
function formatMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Line breaks → paragraphs
    html = html.split('\n\n').map(p => `<p>${p}</p>`).join('');
    html = html.replace(/\n/g, '<br>');
    // Lists
    html = html.replace(/<p>- (.+?)<\/p>/g, '<li>$1</li>');
    return html;
}
