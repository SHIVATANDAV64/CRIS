# CRIS Premium Upgrade — Implementation Plan

**Date:** 2026-05-21
**Components:** Embeddings Service + Streaming Fix + Frontend Redesign

---

## Component 1: pplx-embed-v1-4b on Modal.com (T4 GPU)

**Current State:**
- Search is FTS5 BM25 keyword-only
- Semantic search in search.py:109 is a placeholder returning empty []
- No embeddings infrastructure exists

**Implementation:**

```
modal/
└── embed_service.py          # New Modal deployment for embeddings
    ├── GPU: T4 (float16, ~8GB VRAM)
    ├── Model: pplx-embed-v1-4b via TEI
    ├── Endpoints:
    │   ├── POST /embed       # Batch text embedding
    │   ├── POST /similarity  # Compare two texts
    │   └── GET  /health      # Service health
    └── Batch size: 32 (T4 optimized)

core/
├── embedding_client.py        # New: Modal client wrapper
│   ├── async embed_text(text) → 2560-dim vector
│   ├── async embed_batch(texts) → List[vectors]
│   └── dimension: 2560, binary quantization option
│
└── search_engine.py           # Modified: Add semantic layer
    ├── create_index() → Add embeddings table
    ├── add_embedding(arxiv_id, vector) → SQLite vec0 or separate vectors/
    ├── hybrid_search(query, mode) → BM25 + cosine similarity
    └── cross_domain_discovery(source_id) → Find similar across domains
```

**Database Changes:**
```sql
-- Option A: sqlite-vec extension (fast, native)
CREATE VIRTUAL TABLE paper_embeddings USING vec0(
    arxiv_id TEXT PRIMARY KEY,
    embedding float[2560]
);

-- Option B: File-based JSON (fallback, no extensions)
vectors/
└── {arxiv_id}.json          # {embedding: [0.1, 0.2, ...]}
```

**Success Criteria:**
- [ ] Query "neural ODE" finds papers about differential equations in CS when searched from biology
- [ ] Cross-domain precision@10 > 60% on test queries

---

## Component 2: Proper Streaming Response

**Current State:**
- SSE endpoint exists (chat.py:34) but tokens arrive chunked/delayed
- User wants "live tokens" — seeing each token appear immediately

**Root Cause Analysis:**
- model_client.py:200-292 accumulates chunks before yielding
- ChatService.process_chat_stream() doesn't flush early
- No incremental rendering in frontend

**Implementation:**

```python
# core/model_client.py — Modified _generate_stream()
for chunk in response.iter_lines():
    if chunk:
        data = json.loads(chunk)
        token = data["choices"][0]["delta"].get("content", "")
        if token:
            yield token  # ← IMMEDIATE yield, no buffering


# server/services/chat_service.py — Modified process_chat_stream()
async for chunk in client.generate_stream(...):
    if chunk:  # Turbo check
        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
        # ↑ IMMEDIATE flush, no accumulation


# server/static/app.js — Modified event handling
const eventSource = new EventSource("/api/chat/stream");
let currentMessageDiv = null;

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "token") {
        // ← Append token to CURRENT message, not waiting for full response
        if (!currentMessageDiv) createNewMessage();
        appendTokenToMessage(currentMessageDiv, data.content);
        scrollToBottom();
    }

    if (data.type === "sources") {
        renderSourcesSidecar(data.sources);  # ← Non-blocking
    }
};

// New: Per-token rendering instead of full re-render
function appendTokenToMessage(div, token) {
    const contentSpan = div.querySelector('.message-content-live');
    contentSpan.textContent += token;  // Direct DOM mutation, no innerHTML rebuild
}
```

**Success Criteria:**
- [ ] Tokens appear within 50ms of generation (perceived instant)
- [ ] Sources panel appears async (non-blocking)
- [ ] No visible stutter on long responses (>500 tokens)

---

## Component 3: Premium Research Platform Frontend

**Current State:**
- "3rd class layout" — single sidebar, basic chat, no wiki graph
- "Not having proper control on full settings" — settings panel is minimal
- "Didn't even proper implement that obsidian vault based" — wiki structure exists, no graph visualization

**Design Philosophy:**
- **Research-First UX** — papers and connections are primary, chat is contextual
- **Obsidian-Inspired** — graph view, backlinks, note canvas
- **Premium Feel** — glassmorphism, subtle animations, no stock components

### Layout Redesign

```
┌─────────────────────────────────────────────────────────────────────┐
│  CRIS Premium                               [Search] [User] [Settings] │  ← Header
├────────┬────────────────────────────────────────────────────────────┤
│        │                                                              │
│ KNOW-  │   ┌────────────────────────────────────────────────────┐   │
│ LEDGE  │   │  GRAPH VIEW (Obsidian-style)                       │   │
│  NAV   │   │                                                      │   │
│        │   │    [Paper A] ════► [Concept] ════► [Paper B]       │   │
│ ┌───┐  │   │         │                  │                        │   │
│ │ ▶ │  │   │         ▼                  ▼                        │   │
│ │ ▶ │  │   │    [Related] ◄════► [Domain Bridge]                  │   │
│ │ ▶ │  │   │                                                      │   │
│ └───┘  │   └────────────────────────────────────────────────────┘   │
│ Sources│                                                              │
│ Entities│   [Split View Toggle: Graph | Reader | Assistant]        │
│ Concepts│                                                            │
│ Domains │   ─────────────────────────────────────────────────────   │
│        │                                                              │
│        │   ┌──────────────────────┐  ┌──────────────────────────┐    │
│ AGENT  │   │  PAPER READER        │  │  RESEARCH ASSISTANT      │    │
│ PANEL  │   │                      │  │                          │    │
│        │   │  ╔══════════════╗   │  │  User: Explain the        │    │
│ [Think]│   │  ║  PDF/MD View   ║   │  │       connection          │    │
│ [Search│   │  ║              ║   │  │                            │    │
│ [Plan] │   │  ║  [Synced      ║   │  │  [Animated thinking dots] │    │
│        │   │  ║   scroll]    ║   │  │                            │    │
│        │   │  ╚══════════════╝   │  │  Assistant: Response...   │    │
│        │   │                      │  │  ███ <- Live token stream  │    │
│        │   │  [Citation cards    │  │                            │    │
│        │   │   in sidecar]       │  │  [Sources sidebar]          │    │
│        │   │                      │  │                            │    │
│        │   └──────────────────────┘  └──────────────────────────┘    │
│        │                                                              │
└────────┴────────────────────────────────────────────────────────────┘

Views:
• Graph Mode: Force-directed d3.js with node clusters by domain
• Reader Mode: Split-pane PDF/markdown with embedded citations
• Assistant Mode: Your current chat interface, polished
```

### Key Components to Build

| Component | Description | Status |
|-----------|-------------|--------|
| `GraphView.svelte` | D3.js force-directed graph of papers/concepts/connections | New |
| `PaperReader.svelte` | Citations-enabled markdown reader with backlinks | New |
| `ResearchDeck.svelte` | Sliding panel for research plan management | New |
| `CommandPalette.svelte` | ⌘K modal for quick navigation (Obsidian-style) | New |
| `SettingsPanel.svelte` | Full settings with live validation | Upgrade |

### CSS Framework Upgrade

```css
/* Glassmorphism + Neural gradients */
:root {
  --glass-bg: rgba(15, 23, 42, 0.72);
  --glass-border: rgba(99, 102, 241, 0.15);
  --neural-gradient: linear-gradient(135deg, #06b6d4 0%, #8b5cf6 50%, #3b82f6 100%);
  --syntax-bg: #0d1117;
}

/* Smooth animations */
.token-appear { animation: tokenFade 80ms ease-out; }
.graph-node { transition: transform 200ms cubic-bezier(0.4, 0, 0.2, 1); }
```

### Architecture Decision: Vanilla JS vs Framework

**Option A: Keep Vanilla JS** (faster integration)
- Add cytoscape.js for graph
- Incremental improvements to existing HTML/CSS
- Risk: tech debt accumulates

**Option B: Add Svelte** (recommended)
- Build new components in `frontend/src/`
- Mount Svelte apps into existing DOM nodes
- Gradual migration, keeps existing backend

**Recommendation:** Svelte for Component 3 — it handles reactive state (streaming tokens, graph updates) better than vanilla JS manual DOM manipulation.

---

## Implementation Order

```
Phase 1: Embeddings (Foundation)
├── modal/embed_service.py         # Deploy to Modal T4
├── core/embedding_client.py
├── Add embeddings table to DB
└── hybrid_search() implementation
    └── Manual test: "neural ODE" → CS papers matching biology query

Phase 2: Streaming Fix (Quick Win)
├── Fix model_client.py buffering   # ~30 min change
├── Update chat_service.py          # Immediate yield
├── Update app.js token rendering   # append vs replace
└── Test: 500-token response, check latency

Phase 3: Frontend (Heavy Lift)
├── Set up Svelte build pipeline    # Vite + Svelte
├── Build GraphView component       # D3.js force sim
├── Build PaperReader component     # Markdown citations
├── Integrate with existing chat    # Mount points
├── CSS redesign                    # Glassmorphism theme
└── E2E test: Full research workflow
```

---

## Technical Dependencies

```
# Backend
modal>=0.63.0           # For embedding deployment
text-embeddings-inference  # Or direct transformers
sqlite-vec              # Vector similarity in SQLite (optional)
cosine-similarity       # Python fallback

# Frontend
svelte@5.0.0            # Component framework
d3@7.0                  # Graph visualization
cytoscape.js            # Alternative to D3 for graphs
remark + rehype         # Markdown processing
katex                   # Math rendering
```

---

## Success Criteria Summary

| Component | Metric | Target |
|-----------|--------|--------|
| Embeddings | Cross-domain recall@10 | > 60% |
| Embeddings | Latency (T4) | < 200ms/batch |
| Streaming | Token latency | < 50ms |
| Frontend | Graph nodes rendered | > 100 without lag |
| Frontend | Settings saved/loaded | 100% persistence |
| Integration | Full workflow E2E | Research → Graph → Chat |

---

**Next Step:** Confirm approach, then begin Phase 1 (Embeddings deployment to Modal).
