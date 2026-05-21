# CRIS Premium Frontend Design

**Date:** 2026-05-21
**Status:** Approved
**Approach:** SvelteKit + D3.js

---

## 1. Layout & Architecture

### 1.1 Three-Panel Layout

```
┌─────────────────────────────────────────────────────────────┐
│                     LEFT PANEL (64px)                       │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                          │
│  │Chat │ │Hist │ │Wiki │ │Setng│                          │
│  └─────┘ └─────┘ └─────┘ └─────┘                          │
├─────────────────────────────────────────────────────────────┤
│                    CENTER PANEL                             │
│              (Full height, dynamic content)                 │
└─────────────────────────────────────────────────────────────┘
```

**Left Panel (64px fixed):**
- 4 icon buttons: Chat, History, Wiki, Settings
- Vertical stack, centered icons
- Tooltip on hover showing full name
- Active state: glassmorphism highlight (backdrop-blur, bg-opacity)

**Center Panel (flex-grow):**
- Dynamic content based on route
- URL-based routing: `/chat`, `/history`, `/wiki`, `/settings`
- Supports back button, shareable URLs

**Responsive Behavior:**
- Desktop: Left panel as described
- Mobile (<768px): Left panel collapses to bottom nav bar (64px height)

---

## 2. Components

### 2.1 LeftNav
- 4 icon buttons (SVG icons)
- States: default (muted), hover (glow), active (glassmorphism)
- Tooltip appears on hover after 300ms delay

### 2.2 ChatInterface
- **Input Area**: Bottom-fixed textarea, auto-resize up to 150px
- **Message Area**: Scrollable, shows above input
- **User Message**: Right-aligned, accent color background
- **Assistant Message**: Left-aligned, dark/light bg based on theme
- **Thinking**: Expandable `<thought>` block, italic, opacity 0.7
- **Sources**: Inline cards below assistant messages, clickable
- **Streaming**: Tokens appear live (no buffer)

### 2.3 ChatHistoryList
- Grid layout: 3 columns desktop, 2 tablet, 1 mobile
- **Card Content**:
  - Title (first 50 chars of first message)
  - Preview (first 100 chars of last message)
  - Date (formatted: "2 hours ago", "Yesterday", "May 15")
  - Source count badge
- **Interactions**:
  - Hover: translateY(-2px), box-shadow increase
  - Click: Navigate to `/chat?session=<id>`
  - Right-click: Context menu (Delete, Export)

### 2.4 WikiGraphView
- Full-center D3.js force-directed graph
- **Controls** (top-right overlay):
  - Zoom slider
  - Search input (filter nodes)
  - Toggle physics (pause simulation)
  - Fullscreen button
- **Node Rendering**:
  - Circle radius: 12px
  - Color: by domain category (configurable)
  - Label: on hover, truncate 20 chars
- **Edge Rendering**:
  - 1px stroke, 30% opacity
  - Directional arrows for backlinks

### 2.5 SettingsPanel
- Accordion sections (collapse/expand)
- Each setting: label + input + description tooltip
- Save indicator: "Saved" toast on change
- Import/Export buttons at bottom

---

## 3. Data Flow

### 3.1 State Management

**Svelte Stores:**
```
src/lib/stores/
  ├── navigation.ts   # currentView, route
  ├── chat.ts         # messages, session, streaming
  ├── settings.ts     # user preferences, config
  └── wiki.ts         # graph nodes, edges, currentNode
```

### 3.2 API Integration

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat` | POST | Send message, get response |
| `/api/chat/stream` | GET (SSE) | Streaming response |
| `/api/sessions` | GET | List all chat sessions |
| `/api/sessions/{id}` | GET | Get single session |
| `/api/wiki` | GET | List all wiki entries |
| `/api/wiki/{id}` | GET | Get wiki content |
| `/api/settings` | GET/PATCH | Load/save settings |
| `/api/research/hybrid-search` | POST | Search papers |

### 3.3 Data Persistence

- **Settings**: localStorage (instant) + sync to backend on change
- **Chat History**: Backend only (existing)
- **Wiki Cache**: localStorage with TTL, refresh on demand

---

## 4. Wiki Graph Visualization (Obsidian-Style)

### 4.1 D3.js Force-Directed Graph

**Physics Simulation:**
- Force: link (distance 100), charge (repulsion -300), center
- Collision detection: radius + 5px padding
- Damping: 0.9 for smooth settling

**Rendering:**
- SVG canvas, viewBox for responsiveness
- Only render visible nodes (virtualization for >500 nodes)

### 4.2 Visual Design

| Element | Style |
|---------|-------|
| Background | `#1a1a2e` (dark), grid pattern |
| Node fill | By category: `#7c3aed` (ml), `#059669` (nlp), `#dc2626` (cv), `#2563eb` (other) |
| Node stroke | `#ffffff` 10% opacity |
| Edge stroke | `#ffffff` 30% opacity |
| Text | `#e5e7eb`, font-size 12px |

### 4.3 Interactions

| Action | Behavior |
|--------|----------|
| Click node | Navigate to wiki page in center |
| Drag node | Reposition, physics pauses |
| Scroll | Zoom 0.1x to 4x |
| Right-click | Context menu (Open, New Link, Delete) |
| Search | Filter nodes, highlight matches |

### 4.4 Performance Targets

- Initial load: <2s for 500 nodes
- Frame rate: 60fps during physics
- Interaction latency: <100ms response

---

## 5. Settings System

### 5.1 Setting Categories

**Model Settings:**
| Setting | Type | Default | Range |
|---------|------|---------|-------|
| model_id | dropdown | darwin-opus | darwin-opus, minimax-m2.5 |
| temperature | slider | 0.7 | 0-1 |
| max_tokens | number | 4096 | 512-16384 |
| reasoning | toggle | true | on/off |

**Search Settings:**
| Setting | Type | Default | Range |
|---------|------|---------|-------|
| search_mode | dropdown | hybrid | keyword, semantic, hybrid |
| context_limit | slider | 10 | 5-30 |
| web_search | toggle | true | on/off |
| recency_bias | slider | 0.5 | 0-1 |

**UI Settings:**
| Setting | Type | Default | Range |
|---------|------|---------|-------|
| theme | dropdown | dark | light, dark, system |
| font_size | dropdown | medium | small, medium, large |
| graph_physics | toggle | true | on/off |
| animations | toggle | true | on/off |

**Data Actions:**
- Export all data (JSON download)
- Import data (JSON upload)
- Clear chat history (with confirmation)
- Reset to defaults (with confirmation)

### 5.2 Persistence Strategy

1. User changes setting
2. Instant save to localStorage
3. Debounced (300ms) API sync to backend
4. Show "Saved" toast on API success

---

## 6. Technical Requirements

### 6.1 Tech Stack

- **Framework**: SvelteKit 2.x
- **Graph**: D3.js 7.x
- **Styling**: CSS with custom properties (no Tailwind)
- **Icons**: Lucide Svelte
- **Build**: Vite

### 6.2 Project Structure

```
frontend/
├── src/
│   ├── lib/
│   │   ├── components/
│   │   │   ├── LeftNav.svelte
│   │   │   ├── ChatInterface.svelte
│   │   │   ├── ChatHistoryList.svelte
│   │   │   ├── WikiGraph.svelte
│   │   │   ├── SettingsPanel.svelte
│   │   │   └── ui/           # Button, Input, Toggle, etc.
│   │   └��─ stores/
│   │       ├── navigation.ts
│   │       ├── chat.ts
│   │       ├── settings.ts
│   │       └── wiki.ts
│   ├── routes/
│   │   ├── +layout.svelte
│   │   ├── +page.svelte     # Chat (default)
│   │   ├── history/
│   │   ├── wiki/
│   │   └── settings/
│   └── app.css
├── static/
├── package.json
├── svelte.config.js
└── vite.config.ts
```

---

## 7. Acceptance Criteria

### 7.1 Navigation
- [ ] Left panel shows exactly 4 icons
- [ ] Clicking icon navigates to correct view
- [ ] Active state visible with glassmorphism
- [ ] Back button works correctly

### 7.2 Chat
- [ ] Can send message and receive response
- [ ] Streaming shows tokens live (not buffered)
- [ ] Sources display below responses
- [ ]thinking block is expandable

### 7.3 History
- [ ] Shows grid of past chat sessions
- [ ] Each card shows title, preview, date
- [ ] Clicking card opens that chat
- [ ] Responsive: 3 cols → 2 → 1

### 7.4 Wiki Graph
- [ ] Displays force-directed graph
- [ ] Nodes represent wiki pages
- [ ] Edges represent internal links
- [ ] Click node opens wiki
- [ ] Zoom/pan works
- [ ] Search filters nodes

### 7.5 Settings
- [ ] All settings in Section 5.1 are present
- [ ] Changes persist to localStorage
- [ ] Changes sync to backend
- [ ] Import/export works
- [ ] Theme switch works instantly

---

## 8. Out of Scope (YAGNI)

- User authentication/login
- Real-time collaboration
- Mobile push notifications
- Plugin system
- Mobile native apps
- Offline PWA (future phase)