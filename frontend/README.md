# CRIS Frontend

SvelteKit-based frontend for the CRIS research platform.

## Setup Instructions

### Prerequisites
- Node.js 18+ 
- npm

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

This starts the development server at `http://localhost:5173`.

### Build

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

### Type Checking

```bash
npm run check
```

### Tech Stack
- SvelteKit 2.x
- Svelte 5
- TypeScript
- Vite
- D3 (for visualizations)
- Lucide Svelte (icons)
- @sveltejs/adapter-auto

## Project Structure

```
frontend/
├── src/
│   ├── routes/
│   │   ├── +layout.svelte    # Main layout with navigation
│   │   ├── +page.svelte      # Root redirect to /chat
│   │   ├── chat/             # Chat view
│   │   ├── history/          # History view
│   │   ├── wiki/             # Wiki graph view
│   │   └── settings/         # Settings view
│   ├── app.html              # Base HTML template
│   └── app.d.ts              # Type declarations
├── static/                   # Static assets
├── package.json
├── svelte.config.js
├── vite.config.ts
└── tsconfig.json
```

## Routes

- `/` - Redirects to `/chat`
- `/chat` - Main chat interface
- `/history` - Research session history
- `/wiki` - Wiki knowledge graph
- `/settings` - Application settings