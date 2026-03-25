# Engram Web UI — Design Specification

## Overview

A personal dashboard for interacting with, curating, and visualizing your engram. Built with Next.js (App Router) + Mantine v7 + Mantine Charts + D3.js, living in `web/` within the engram monorepo. Connects to the existing FastAPI backend at `localhost:8000`.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Framework | Next.js 14+ (App Router) |
| UI Library | Mantine v7 (dark theme default) |
| Charts | Mantine Charts (Recharts wrapper) |
| Network Graph | D3.js (people/topic visualization only) |
| Styling | Mantine's built-in CSS modules |
| HTTP Client | fetch wrapper with token auth |
| State | React state + SWR or TanStack Query for API caching |
| Package Manager | npm or pnpm |

---

## Architecture

### Project Location
```
engram/
├── src/engram/          # Existing Python backend
├── web/                 # NEW: Next.js frontend
│   ├── app/             # App Router pages
│   │   ├── layout.tsx   # Root layout with sidebar
│   │   ├── page.tsx     # Dashboard (/)
│   │   ├── chat/
│   │   ├── memories/
│   │   ├── identity/
│   │   ├── people/
│   │   ├── data/
│   │   └── settings/
│   ├── components/      # Shared components
│   │   ├── layout/      # Sidebar, header, nav
│   │   ├── chat/        # Chat UI components
│   │   ├── memories/    # Memory cards, filters
│   │   ├── identity/    # Belief cards, timeline
│   │   ├── people/      # Graph, person detail
│   │   ├── data/        # Import forms, job status
│   │   └── common/      # Shared UI (source icon, confidence bar, etc.)
│   ├── lib/             # Utilities
│   │   ├── api.ts       # API client wrapper
│   │   ├── auth.ts      # Token management
│   │   └── types.ts     # TypeScript types matching API responses
│   ├── hooks/           # Custom React hooks
│   ├── next.config.js
│   ├── package.json
│   └── tsconfig.json
└── ...
```

### API Connection

The Next.js app connects to FastAPI at `http://localhost:8000`. All API calls go through a thin client wrapper (`lib/api.ts`) that:
- Reads the bearer token from a cookie (`engram_token`)
- Adds `Authorization: Bearer <token>` to every request
- Handles 401 (redirect to token entry page)
- Provides typed response wrappers

### Authentication Flow

1. First visit: user sees a "Connect to Engram" page with a token input field
2. User pastes their engram owner token
3. App validates by calling `GET /api/identity/profile`
4. On success: stores token in localStorage (`engram_token`), redirects to dashboard. Note: localStorage (not httpOnly cookie) because this is a purely client-side app talking directly to the FastAPI backend — no Next.js server-side proxy.
5. On failure: shows error, lets user retry
6. "Generate New Token" link → calls `POST /api/tokens` (requires existing valid token) or shows CLI instructions (`uv run engram init` to generate a new token)

---

## Pages

### 1. Dashboard (`/`)

**Purpose:** Overview of the engram's state + quick interaction.

**Components:**
- **Stats cards** (top row, 4 cards): Total memories, People, Active beliefs, Topics. Each from `GET /api/memories/stats` and `GET /api/identity/beliefs`.
- **Memories by source** (donut chart): Visual breakdown of memory counts by platform. Mantine Charts DonutChart.
- **Recent memories** (left column): Last 10 memories with source icon, timestamp, content snippet. From `GET /api/memories?limit=10`.
- **Quick chat** (right column): Compact chat widget. Send a message via `POST /api/engram/ask`, show response inline. Links to full chat page.
- **Memory timeline** (bottom): Area chart showing memory creation over time (by month). Mantine Charts AreaChart.

### 2. Chat (`/chat`)

**Purpose:** Full conversation interface with your engram.

**Components:**
- **Message list**: Scrollable, full-height. User messages right-aligned, engram responses left-aligned.
- **Engram response card**: Shows answer text, confidence badge, caveats. Expandable "Sources" section showing cited memory IDs (clickable → navigates to `/memories/<id>` detail view), cited belief IDs (clickable → navigates to `/identity` beliefs tab).
- **Input bar** (bottom): Text input + send button. Optional "as of date" picker (DatePicker from Mantine) that passes `as_of_date` to the API.
- **Suggested questions** (above input when conversation is empty): Based on `GET /api/engram/topics`, suggest "What do you think about [top topic]?", "Tell me about [person]", etc.
- **Conversation history**: Stored in localStorage. Clear button to reset.

**API calls:**
- `POST /api/engram/ask` — `{query, as_of_date?}`
- `GET /api/engram/topics` — for suggestions

### 3. Memories (`/memories`)

**Purpose:** Browse, search, filter, edit, and manage memories.

**Components:**
- **Search + filter bar** (top):
  - Text search input (sends `q` param)
  - Source filter: multi-select (Gmail, Reddit, Facebook, Instagram)
  - Topic filter: autocomplete search (from `GET /api/engram/topics`)
  - Person filter: autocomplete search
  - Date range picker
  - Visibility toggle: active / private / excluded / all
  - Sort dropdown: date, importance, reinforcement count
- **Stats bar**: Total results, source breakdown mini-donut
- **Memory card list** (scrollable):
  - Each card: source icon, timestamp, content (truncated), intent badge, importance bar, topic tags, people chips
  - Click to expand: full content, meaning, interaction_context, full metadata, linked topics/people, parent/child evolution chain
- **Memory detail actions** (in expanded view):
  - Edit: content, visibility, importance (inline editing)
  - Reinforce / Degrade / Evolve buttons (open modal for evidence/nuance input)
  - Delete (with confirmation)
  - Set visibility: active / private / excluded

**API calls:**
- `GET /api/memories?q=&topic=&person=&source=&limit=&...`
- `GET /api/memories/{id}`
- `PUT /api/memories/{id}`
- `DELETE /api/memories/{id}`
- `POST /api/memories/{id}/reinforce`
- `POST /api/memories/{id}/degrade`
- `POST /api/memories/{id}/evolve`
- `GET /api/memories/stats`

### 4. Identity (`/identity`)

**Purpose:** View, edit, and visualize beliefs, preferences, and style.

**Components:**

**Tabs: Beliefs | Preferences | Style | Snapshots**

**Beliefs tab:**
- **Timeline chart** (top): Select a topic from dropdown → Mantine LineChart showing belief confidence over time (x=date, y=confidence). Data from `GET /api/identity/timeline?topic=`.
- **"Run Inference" button**: Calls `POST /api/identity/infer`. Shows loading state, refreshes beliefs on completion.
- **Belief card list**:
  - Each card: topic (bold), stance, nuance (italic), confidence bar (0-1), source badge (inferred / user)
  - Click to expand: full detail, supporting memories (if available), mini evolution timeline
  - Actions: edit (inline), delete, "Set as User Override"
- **"Add Belief" button**: Modal form with topic, stance, nuance, confidence fields.

**Preferences tab:**
- Card list grouped by category
- Each: category label, value, strength bar, source badge
- Edit/delete/add actions
- Inline editing

**Style tab:**
- Visual gauges: humor_level, verbosity, formality (Mantine Slider or Progress components, 0-1 scale)
- Tone display (text)
- Vocabulary notes (editable textarea)
- Communication patterns (editable textarea)
- "Override" button (sets source="user")

**Snapshots tab:**
- Table: snapshot ID, label, created_at
- Click to view: shows the frozen identity JSON in a formatted display
- "Take Snapshot" button
- "Compare" mode: select two snapshots, show side-by-side diff (client-side JSON comparison — no dedicated backend endpoint needed)

**API calls:**
- `GET /api/identity/beliefs?topic=&as_of_date=`
- `POST /api/identity/beliefs`
- `PUT /api/identity/beliefs/{id}`
- `DELETE /api/identity/beliefs/{id}`
- `GET /api/identity/timeline?topic=&start=&end=`
- `POST /api/identity/infer`
- `GET /api/identity/preferences`
- `POST /api/identity/preferences`
- `PUT /api/identity/preferences/{id}`
- `DELETE /api/identity/preferences/{id}`
- `GET /api/identity/style`
- `PUT /api/identity/style`
- `POST /api/identity/snapshot`
- `GET /api/identity/snapshots`
- `GET /api/identity/snapshot/{id}`

### 5. People & Relationships (`/people`)

**Purpose:** Browse social graph, visualize relationships.

**Components:**

**Tabs: List View | Graph View**

**List View:**
- Searchable, sortable table (Mantine DataTable or similar)
- Columns: Name, Relationship type, Platform(s), Message count, Interaction score (progress bar), Connected since
- Sort by any column
- Click row → opens Person Detail panel

**Graph View (D3.js):**
- Force-directed graph
- Center node: You
- Surrounding nodes: People, sized by interaction_score
- Edge thickness: message_count / interaction_strength
- Node colors by platform (Gmail=red, Facebook=blue, Instagram=purple, Reddit=orange)
- Interactions: click node → detail panel, hover → tooltip, zoom/pan, drag
- Filters: minimum interaction score slider, platform toggles, relationship type filter

**Person Detail Panel** (slide-out drawer):
- Name, relationship type (editable dropdown)
- Platform badges, connected since date
- Stats: message count, interaction score, first/last interaction
- Memories involving this person (scrollable list, from `GET /api/memories?person=`)
- Photos with this person
- Common topics (derived from shared memory topics)

**API calls:**
- `GET /api/memories?person=` (for person's memories)
- Direct DB queries needed: The current API doesn't have a dedicated `/api/people` endpoint. **We need to add:**
  - `GET /api/people?q=&sort=&limit=` — list/search people with relationship data
  - `GET /api/people/{id}` — person detail with relationship, memory count, top topics
  - `PUT /api/people/{id}` — edit relationship type
  - `GET /api/people/{id}/memories` — memories involving this person
  - `GET /api/people/graph` — returns nodes + edges for D3 visualization

### 6. Data Management (`/data`)

**Purpose:** Import data, monitor ingestion, manage sources.

**Components:**

**Import section:**
- Platform cards (Gmail, Reddit, Facebook, Instagram, File Upload)
- Each shows: icon, last import date, memory count, status badge
- "Import" button → modal with:
  - Export directory path input
  - Platform-specific instructions (expandable, same as CLI wizard)
  - "Validate" button → calls `POST /api/ingest/export/validate` to check path
  - "Register Export" button → calls `POST /api/ingest/export` to register the path
  - "Process" button → triggers background ingestion (separate from registration)
- File upload: drag-and-drop zone for txt/md/json

**Ingestion Jobs table:**
- Columns: Job ID, Source, Status (with color badge), Items processed, Errors, Started, Duration
- Auto-refresh while jobs are running
- Click failed job → error detail

**Source Visibility section:**
- Table: source type, source_ref, memory count, current visibility
- Bulk actions toolbar: select multiple → set visibility
- Per-source buttons: active / private / excluded

**API calls:**
- `POST /api/ingest/file` (multipart upload)
- `POST /api/ingest/export` — `{platform, export_path}`
- `GET /api/ingest/status?job_id=`
- `GET /api/ingest/exports`
- `GET /api/sources`
- `PUT /api/sources/visibility`
- `POST /api/sources/bulk`

### Settings (`/settings`)

**Purpose:** API keys, tokens, model config, export/import.

**Sections:**
- **API Keys**: Redacted display from `GET /api/config`, update form via `PUT /api/config/keys`
- **Access Tokens**: List from `GET /api/tokens`, create via `POST /api/tokens`, revoke via `DELETE /api/tokens/{id}`. New token displayed once in a modal.
- **Model Config**: Display generation model, embedding model, provider
- **Export Engram**: Button → `POST /api/engram/export`, download as JSON file
- **Import Engram**: Upload JSON → `POST /api/engram/import`

---

## New API Endpoints Required

The existing backend needs these additional endpoints for the web UI:

### People API (`/api/people`)
```
GET  /api/people?q=&sort=&limit=&offset=    # List/search people with relationship data
GET  /api/people/{id}                         # Person detail
PUT  /api/people/{id}                         # Edit person (relationship_type, name)
GET  /api/people/{id}/memories                # Memories involving this person
GET  /api/people/graph                        # Nodes + edges for D3 network graph
```

### Streaming Chat
```
POST /api/engram/ask/stream                   # SSE streaming response (future enhancement)
```

For MVP, non-streaming `POST /api/engram/ask` is fine. Streaming can be added later.

---

## Shared Components

### SourceIcon
Renders platform icon (Gmail envelope, Reddit alien, Facebook f, Instagram camera, File doc).

### ConfidenceBar
Mantine Progress component showing 0-1 confidence/importance as a colored bar.

### TopicTag
Clickable badge that links to memories filtered by that topic.

### PersonChip
Clickable avatar chip that links to the person detail page.

### MemoryCard
Reusable card component used in dashboard, memories page, and person detail. Compact and expanded variants.

### BeliefCard
Reusable for beliefs tab and chat source citations.

### DateRangePicker
Mantine DatePickerInput for filtering by time range.

### AsOfDatePicker
Single date picker for temporal queries ("respond as of this date").

---

## Build Order

1. **Project scaffold** — Next.js + Mantine + TypeScript setup in `web/`
2. **Layout + auth** — Sidebar, token entry, API client wrapper
3. **Dashboard** — Stats cards, recent memories, quick chat, source donut chart
4. **Chat page** — Full conversation UI with citations
5. **Memories page** — Search, filter, browse, edit
6. **Identity page** — Beliefs/preferences/style with timeline chart
7. **People API** — Add `/api/people` endpoints to FastAPI backend
8. **People page** — List view + D3 graph
9. **Data page** — Import, jobs, source visibility
10. **Settings page** — Tokens, keys, export/import

---

## Backend Enhancements Required

The existing FastAPI backend needs these additions before the web UI is fully functional. These should be built as part of the web UI implementation (step 7 in build order covers people API; other enhancements happen alongside the page that needs them).

### Enhanced Memory Search (`GET /api/memories`)

Current params: `q`, `topic`, `person`, `source` (single), `limit`. Needs:
- `sources` (comma-separated, replaces single `source`) — multi-source filter
- `visibility` — filter by active/private/excluded
- `sort` — date, importance, reinforcement_count (default: date desc)
- `date_from`, `date_to` — date range filter
- `offset` — pagination

### Memory Detail Response

Add `interaction_context` to the memory detail response (`GET /api/memories/{id}`). The field exists on the model but may not be in the serialization.

### Aggregated Stats

New endpoint or enhanced existing:
- `GET /api/memories/stats/timeline?bucket=month` — returns `[{month: "2024-01", count: 42}, ...]` for the dashboard AreaChart
- `GET /api/memories/stats` should also return `belief_count` (or the dashboard makes two calls — acceptable)

### Ingestion Jobs List

- `GET /api/ingest/jobs?limit=&status=` — list all ingestion jobs (not just single lookup). Needed for the Data page jobs table.

### Export Validation + Processing

- `POST /api/ingest/export/validate` — validate an export path exists and the parser recognizes it. Returns `{valid: bool, platform: str, file_count: int}`.
- Clarify that `POST /api/ingest/export` registers the export. A separate `POST /api/ingest/export/{id}/process` or background trigger starts actual processing.

### People API

As listed in the spec above:
```
GET  /api/people?q=&sort=&limit=&offset=
GET  /api/people/{id}
PUT  /api/people/{id}
GET  /api/people/{id}/memories
GET  /api/people/graph
```

### Photos by Person

- `GET /api/photos?person_id=` — filter photos by person (via photo_people join). Needed for Person Detail panel.

### CORS Middleware

Add FastAPI CORS middleware to `main.py`:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Design Tokens (Mantine v7 Theme)

```typescript
import { createTheme, MantineProvider } from '@mantine/core';

const theme = createTheme({
  primaryColor: 'blue',
  defaultRadius: 'md',
  fontFamily: 'Inter, system-ui, sans-serif',
  headings: { fontFamily: 'Inter, system-ui, sans-serif' },
});

// In layout.tsx:
// <MantineProvider theme={theme} defaultColorScheme="dark">
```

Dark theme by default via `defaultColorScheme="dark"` on MantineProvider. User can toggle light mode via Mantine's `useComputedColorScheme` + `useMantineColorScheme` hooks.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| API latency for chat | Show loading state, add streaming later |
| Large memory lists | Paginate (limit/offset), virtual scrolling for 1000+ results |
| D3 graph performance with 2000+ nodes | Filter by minimum interaction score, lazy-load on zoom |
| Token management | Clear error messages, easy regeneration via CLI fallback |
| CORS | Configure FastAPI CORS middleware to allow localhost:3000 |
