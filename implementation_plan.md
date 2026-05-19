# CRIS UI Overhaul — Cohere Design System Implementation

> Transform the CRIS frontend from a "plain coat over vanilla HTML" to a **premium, Cohere-inspired enterprise AI interface** that matches the design system in `DESIGN.md`.

---

## Current State vs. Target

| Aspect | Current (Problem) | Target (Cohere DESIGN.md) |
|--------|-------------------|---------------------------|
| **Typography** | Generic `Inter` only, uniform sizes | **Space Grotesk** (display headlines) + **Inter** (body/UI) — tight tracking, dramatic size contrast |
| **Color Palette** | Muted grays, no personality | Deep green `#003c33`, near-black `#17171c`, coral `#ff7759`, stone `#eeece7` — enterprise warmth |
| **Layout** | Cramped sidebar, dense chat | **Editorial whitespace**, wide breathing room, centered content, dramatic vertical spacing |
| **Components** | Generic inputs/buttons, no hierarchy | **Pill CTAs**, dark feature bands, research-table patterns, source credibility chips |
| **Surfaces** | Flat monotone layers | **Surface alternation** — white canvas ↔ deep green bands ↔ stone cards, rounded media |
| **Micro-animations** | Basic fadeIn only | Smooth hover lifts, border color transitions, stagger animations, pulse indicators |
| **Welcome Screen** | Small centered text card | **Monumental hero** with display typography, capability cards in grid, feature band |
| **Overall Feel** | Generic developer tool | **Premium research command center** like Cohere's product pages |

---

## Proposed Changes

### Font Loading

#### [MODIFY] [index.html](file:///c:/Users/rudra/Downloads/CRIS-Start/frontend/index.html)

- Replace Google Fonts link to load **Space Grotesk** (display headlines) + **Inter** (body/UI) + **JetBrains Mono** (code/labels)
- Space Grotesk serves as the open-source analogue to CohereText — same geometric monospace-feeling display character
- This gives us the **display vs. body type split** that defines the Cohere aesthetic

---

### Design System CSS — Complete Rewrite

#### [MODIFY] [index.css](file:///c:/Users/rudra/Downloads/CRIS-Start/frontend/src/index.css)

Complete rewrite of the stylesheet. Key changes:

**1. CSS Custom Properties (Design Tokens)**
- Colors: Full Cohere palette — `--cohere-black`, `--deep-green`, `--canvas`, `--soft-stone`, `--coral`, `--action-blue`, `--ink`, `--muted`, `--hairline`
- Typography: Font stacks — `--font-display` (Space Grotesk), `--font-body` (Inter), `--font-mono` (JetBrains Mono)
- Spacing: 8px base grid with `--space-xs` through `--space-section` (80px)
- Radius: `--radius-xs` (4px) through `--radius-pill` (32px) and `--radius-full` (9999px)
- Shadows: Minimal — borders and surface contrast do the work (Cohere is flat)

**2. Dark Mode**
- Dark mode uses `#0d0d0f` backgrounds (near-black) with deep green accents
- Coral `#ff7759` becomes the primary accent in dark mode (replaces blue)
- Cards get subtle translucent borders like Cohere's dark product bands

**3. Sidebar — Complete Redesign**
- Deep green (`#003c33`) gradient background in dark mode (like Cohere's product bands)
- White/stone background in light mode
- Logo area: Larger, with Space Grotesk title + mono subtitle
- New Chat button: Pill-shaped (32px radius), near-black fill, 14px weight-500
- Tabs: Uppercase mono labels (12px, 0.06em tracking) with bottom-border active indicator
- History items: Wider padding, rule-separated (hairline borders), no background hover — just border-left accent
- Footer: Clean model badge with status dot, pill model selector, version in micro text

**4. Chat Area — Transformed**
- Header: Minimal — title in Space Grotesk display weight, subtle subtitle below
- Messages: Max-width 760px centered, generous 32px vertical spacing
- User messages: Right-aligned, soft-stone `#eeece7` background, 16px radius
- Assistant messages: Left-aligned, no background, clean typography flow
- Message labels: Uppercase mono labels (CohereMono style, 12px, `#93939f`)
- Thinking blocks: Deep green band with white text (like dark-feature-band)
- Source chips: Coral taxonomy chips (like blog-filter-chip) with pill outline

**5. Welcome Screen — Monumental Hero**
- Display headline: 48-60px Space Grotesk, tight line height (1.0), negative tracking (-1.2px)
- Subtitle: 18px Inter, `#616161`, generous whitespace below
- Feature grid: 3-column capability cards with thin-line icons, 24px headings, body text
- Dark feature band: Full-width deep green section with white text showcasing key capabilities
- Trust indicator strip with mono labels

**6. Input Area — Premium**
- Rounded input container (22px radius) with soft border
- Focus state: Border turns coral in dark mode, blue in light mode
- Send button: Pill-shaped, near-black, with arrow icon
- Hint text: Micro typography (12px, muted)

**7. Scrollbars**
- Ultra-thin (3px), matches border-subtle
- On hover widens to 5px with smooth transition

**8. Animations & Micro-interactions**
- Messages: Stagger fade-in with translateY(8px)
- Buttons: Scale(0.98) on active, smooth border-color transitions
- Sidebar items: Border-left accent slides in on hover
- Thinking indicator: Coral pulsing icon (already exists, refined)
- Modal: Backdrop blur + scale-in animation
- Cards: Subtle lift on hover via border-color change (no shadows, Cohere is flat)

---

### Component JSX Updates

#### [MODIFY] [ChatPanel.tsx](file:///c:/Users/rudra/Downloads/CRIS-Start/frontend/src/components/ChatPanel.tsx)

- Upgrade welcome screen to monumental hero with display typography + capability cards
- Add animated gradient accent bar to the header
- Improve message layout with better spacing and labels
- Add typing indicator animation refinement
- Wrap sources in proper taxonomy-chip layout

#### [MODIFY] [Sidebar.tsx](file:///c:/Users/rudra/Downloads/CRIS-Start/frontend/src/components/Sidebar.tsx)

- Redesign logo section with larger brand mark and Space Grotesk title
- Add decorative subtle gradient accent line below logo
- Improve tab navigation with mono labels and active indicators
- Enhance model selector dropdown with proper elevation

#### [MODIFY] [MemoryPanel.tsx](file:///c:/Users/rudra/Downloads/CRIS-Start/frontend/src/components/MemoryPanel.tsx)

- Upgrade stat cards to use dark feature band style
- Entity type badges: Pill-shaped with Cohere taxonomy colors
- Section headers: Uppercase mono labels with hairline dividers

#### [MODIFY] [SourcesBrowser.tsx](file:///c:/Users/rudra/Downloads/CRIS-Start/frontend/src/components/SourcesBrowser.tsx)

- Convert to research-table layout: Rule-separated rows with title left, category pills centered, date right
- Paper modal: Refined with better typography hierarchy and rounded media-card style

#### [MODIFY] [SettingsPanel.tsx](file:///c:/Users/rudra/Downloads/CRIS-Start/frontend/src/components/SettingsPanel.tsx)

- Form styling: Clean rectangular inputs with thin gray borders, form-focus-violet border on focus
- Section cards: Subtle separation with hairline borders
- Pill CTA buttons for save/reset

---

## Typography Mapping

Since CohereText and Unica77 are proprietary, we use the documented fallbacks:

| DESIGN.md Role | Font Family | Our Implementation |
|---|---|---|
| Hero Display | CohereText | **Space Grotesk** (same geometric monospace-feeling character) |
| Product Display | CohereText | **Space Grotesk** |
| Section Display | Unica77 | **Inter** (recommended fallback) |
| Body/UI | Unica77 | **Inter** |
| Mono labels | CohereMono | **JetBrains Mono** |

---

## Open Questions

> [!IMPORTANT]  
> **Theme Preference**: The Cohere design is primarily a **light-mode, white-canvas** design with dark bands as accents. Your current app defaults to **dark mode**. Should we:
> - A) Keep dark mode as default but significantly improve it with deep-green accents?
> - B) Switch to light mode as default (closer to Cohere's actual look)?
> - C) Make both equally polished (recommended — I'll do both)?

> [!IMPORTANT]
> **Scope Confirmation**: This plan covers **Phase 1** of UPGRADE_PLAN_REVISED.md — the Vite UI upgrade with the Cohere DESIGN.md aesthetic. It does NOT touch the backend, API endpoints, or add new features like the Research Engine (Phase 2). Confirming this is what you want first?

---

## Verification Plan

### Visual Testing
- Launch with `npm run dev` in frontend directory
- Screenshot comparison against the Cohere design reference
- Test both dark and light themes
- Test at 320px, 768px, 1024px, 1440px breakpoints

### Functional Testing  
- All existing features preserved: chat, history, memory panel, sources browser, settings, web search
- Keyboard shortcuts still work (Ctrl+N, Ctrl+E, Enter, Shift+Enter)
- Markdown rendering with syntax highlighting
- SSE streaming with thinking indicator
- Paper drag-and-drop to chat
- Session management (create, load, delete, export)
- Theme toggle and persistence
- Model selector dropdown

### Build Validation
- `npx tsc --noEmit` — no TypeScript errors
- `npm run build` — clean production build
