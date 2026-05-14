// CRIS Chat Interface — Client-side logic with conversation memory

const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

// Session ID for conversation continuity
let sessionId = null;

// ── Load stats on page load ─────────────────────────────────────────────
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
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                use_reasoning: true,
                session_id: sessionId,  // Send session ID for conversation continuity
            }),
        });

        const data = await resp.json();

        // Store session ID from server response
        if (data.session_id) {
            sessionId = data.session_id;
        }

        removeLoading(loadingId);
        addAssistantMessage(data);
    } catch (e) {
        removeLoading(loadingId);
        addMessage('assistant', 'Connection error. Is the server running?');
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

function addAssistantMessage(data) {
    const div = document.createElement('div');
    div.className = 'message assistant-message';

    let thinkingHTML = '';
    if (data.thinking) {
        const thinkId = 'think-' + Date.now();
        thinkingHTML = `
            <button class="thinking-toggle" onclick="toggleThinking('${thinkId}', this)">
                <span class="arrow">▶</span>
                <span>Reasoning trace (${data.thinking.length} chars)</span>
            </button>
            <div class="thinking-content" id="${thinkId}">${escapeHtml(data.thinking)}</div>
        `;
    }

    let sourcesHTML = '';
    if (data.sources && data.sources.length > 0) {
        // Filter out concept: entries for cleaner display
        const paperSources = data.sources.filter(s => !s.arxiv_id.startsWith('concept:'));
        const conceptSources = data.sources.filter(s => s.arxiv_id.startsWith('concept:'));

        if (paperSources.length > 0) {
            const chips = paperSources.map(s => {
                const typeClass = s.contribution_type || '';
                const typeLabel = s.contribution_type ?
                    `<span class="source-type ${typeClass}">${s.contribution_type}</span>` : '';
                return `<span class="source-chip">${typeLabel} ${s.arxiv_id}</span>`;
            }).join('');

            sourcesHTML = `
                <div class="sources-section">
                    <div class="sources-title">Sources (${paperSources.length} papers${conceptSources.length > 0 ? `, ${conceptSources.length} concepts` : ''})</div>
                    ${chips}
                </div>
            `;
        }
    }

    const modeLabel = data.mode ? ` • ${data.mode}` : '';
    const tokenLabel = data.tokens_used ? ` • ${data.tokens_used} tokens` : '';

    div.innerHTML = `
        <div class="message-content">
            <div class="message-label">CRIS${modeLabel}${tokenLabel}</div>
            ${thinkingHTML}
            <div class="message-text">${formatMarkdown(data.response)}</div>
            ${sourcesHTML}
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

function toggleThinking(id, btn) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.toggle('visible');
        btn.classList.toggle('expanded');
    }
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('visible');
    sidebar.classList.toggle('hidden');
}

// ── Simple markdown formatting ──────────────────────────────────────────
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

function escapeHtml(text) {
    const el = document.createElement('div');
    el.textContent = text;
    return el.innerHTML;
}
