# Engram Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Next.js personal dashboard for interacting with, curating, and visualizing the engram — including chat, memory browser, identity management, people graph, and data import.

**Architecture:** Next.js 14 App Router + Mantine v7 in a `web/` directory within the engram monorepo. Connects to the existing FastAPI backend at localhost:8000 via a typed API client with bearer token auth from localStorage. Backend enhancements (CORS, new endpoints) are built alongside the pages that need them.

**Tech Stack:** Next.js 14+, TypeScript, Mantine v7, Mantine Charts, D3.js, SWR for data fetching

**Spec:** `docs/superpowers/specs/2026-03-24-engram-web-ui-design.md`

---

## File Map

```
web/
├── app/
│   ├── layout.tsx              # Root layout: MantineProvider + sidebar shell
│   ├── page.tsx                # Dashboard (/)
│   ├── auth/
│   │   └── page.tsx            # Token entry page (/auth)
│   ├── chat/
│   │   └── page.tsx            # Chat interface (/chat)
│   ├── memories/
│   │   ├── page.tsx            # Memory browser (/memories)
│   │   └── [id]/
│   │       └── page.tsx        # Memory detail (/memories/[id])
│   ├── identity/
│   │   └── page.tsx            # Identity dashboard with tabs (/identity)
│   ├── people/
│   │   ├── page.tsx            # People list + graph tabs (/people)
│   │   └── [id]/
│   │       └── page.tsx        # Person detail (/people/[id])
│   ├── data/
│   │   └── page.tsx            # Data management (/data)
│   └── settings/
│       └── page.tsx            # Settings (/settings)
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx        # Mantine AppShell with sidebar nav
│   │   └── Sidebar.tsx         # Navigation sidebar
│   ├── common/
│   │   ├── SourceIcon.tsx      # Platform icon (Gmail/Reddit/FB/IG)
│   │   ├── ConfidenceBar.tsx   # 0-1 progress bar
│   │   ├── TopicTag.tsx        # Clickable topic badge
│   │   └── PersonChip.tsx      # Clickable person avatar chip
│   ├── chat/
│   │   ├── MessageList.tsx     # Chat message bubbles
│   │   ├── ChatInput.tsx       # Input bar with as-of-date picker
│   │   └── SourceCitations.tsx # Expandable cited sources
│   ├── memories/
│   │   ├── MemoryCard.tsx      # Memory card (compact + expanded)
│   │   ├── MemoryFilters.tsx   # Search + filter bar
│   │   └── MemoryActions.tsx   # Reinforce/degrade/evolve buttons
│   ├── identity/
│   │   ├── BeliefCard.tsx      # Belief with edit/timeline
│   │   ├── PreferenceCard.tsx  # Preference with edit
│   │   ├── StyleGauges.tsx     # Humor/verbosity/formality sliders
│   │   └── BeliefTimeline.tsx  # Mantine LineChart for belief evolution
│   ├── people/
│   │   ├── PeopleTable.tsx     # Sortable people list
│   │   ├── PersonDetail.tsx    # Person detail drawer
│   │   └── RelationshipGraph.tsx # D3 force-directed graph
│   └── data/
│       ├── PlatformCard.tsx    # Import platform card
│       ├── JobsTable.tsx       # Ingestion jobs status
│       └── SourceManager.tsx   # Source visibility controls
├── lib/
│   ├── api.ts                  # Typed API client wrapper
│   ├── auth.ts                 # Token read/write/validate
│   └── types.ts                # TypeScript types for API responses
├── hooks/
│   ├── useApi.ts               # SWR-based data fetching hook
│   └── useAuth.ts              # Auth state hook
├── CLAUDE.md                   # Project guide for web app
├── next.config.ts
├── package.json
└── tsconfig.json
```

Backend files to modify/create:
```
src/engram/main.py              # Add CORS middleware
src/engram/api/routes/memories.py  # Enhanced search params
src/engram/api/routes/people.py    # NEW: People API
src/engram/api/routes/ingest.py    # Jobs list + validate endpoint
src/engram/api/routes/photos.py    # Person filter
src/engram/api/routes/__init__.py  # Register people router
tests/test_api/test_people.py      # NEW: People API tests
```

---

## Task 1: Project Scaffold + CLAUDE.md

**Files:**
- Create: `web/package.json`
- Create: `web/next.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/app/layout.tsx`
- Create: `web/app/page.tsx`
- Create: `web/CLAUDE.md`

- [ ] **Step 1: Initialize Next.js project**

```bash
cd /home/bsambrone/repos/engram
npx create-next-app@latest web --typescript --tailwind=no --eslint --app --src-dir=no --import-alias="@/*"
```

- [ ] **Step 2: Install Mantine and dependencies**

```bash
cd web
npm install @mantine/core @mantine/hooks @mantine/charts @mantine/dates @mantine/notifications recharts dayjs swr d3 @types/d3
npm install -D postcss postcss-preset-mantine
```

- [ ] **Step 3: Configure PostCSS for Mantine**

Create `web/postcss.config.mjs`:
```javascript
const config = {
  plugins: {
    'postcss-preset-mantine': {},
  },
};
export default config;
```

- [ ] **Step 4: Create root layout with MantineProvider**

`web/app/layout.tsx`:
```tsx
import '@mantine/core/styles.css';
import '@mantine/charts/styles.css';
import '@mantine/dates/styles.css';
import '@mantine/notifications/styles.css';
import { ColorSchemeScript, MantineProvider, createTheme } from '@mantine/core';
import { Notifications } from '@mantine/notifications';

const theme = createTheme({
  primaryColor: 'blue',
  defaultRadius: 'md',
  fontFamily: 'Inter, system-ui, sans-serif',
  headings: { fontFamily: 'Inter, system-ui, sans-serif' },
});

export const metadata = { title: 'Engram', description: 'Your digital engram' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-mantine-color-scheme="dark">
      <head>
        <ColorSchemeScript defaultColorScheme="dark" />
      </head>
      <body>
        <MantineProvider theme={theme} defaultColorScheme="dark">
          <Notifications />
          {children}
        </MantineProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Create placeholder home page**

`web/app/page.tsx`:
```tsx
import { Title, Text, Container } from '@mantine/core';

export default function Home() {
  return (
    <Container size="md" py="xl">
      <Title>Engram</Title>
      <Text c="dimmed">Your digital engram dashboard. Setting up...</Text>
    </Container>
  );
}
```

- [ ] **Step 6: Create web/CLAUDE.md**

`web/CLAUDE.md`:
```markdown
# Engram Web UI

Next.js frontend for the Engram platform. See [../ENGRAMDESIGN.md](../ENGRAMDESIGN.md) for full backend architecture.

## Quick Reference

```bash
cd web
npm install              # Install dependencies
npm run dev              # Start dev server (port 3000)
npm run build            # Production build
npm run lint             # Lint
```

## Architecture

- **Next.js 14** with App Router (all pages in `app/`)
- **Mantine v7** for UI components, dark theme default
- **Mantine Charts** (Recharts wrapper) for standard charts
- **D3.js** for the relationship network graph only
- **SWR** for API data fetching with caching
- Connects to FastAPI backend at `http://localhost:8000`

## Key Files

| What | Where |
|------|-------|
| Root layout (MantineProvider) | `app/layout.tsx` |
| API client (typed, auth) | `lib/api.ts` |
| Auth (token management) | `lib/auth.ts` |
| TypeScript API types | `lib/types.ts` |
| Sidebar navigation | `components/layout/Sidebar.tsx` |
| All page routes | `app/{page,chat,memories,identity,people,data,settings}/` |

## Auth

Token stored in localStorage (`engram_token`). Every API call reads from localStorage and adds `Authorization: Bearer <token>`. If 401, redirects to `/auth`.

## API

All calls go through `lib/api.ts` which wraps fetch with:
- Base URL: `http://localhost:8000`
- Auto auth header from localStorage
- Typed responses
- 401 → redirect to /auth

## Backend Requirements

The FastAPI backend must have CORS enabled for `http://localhost:3000`. See the spec at `docs/superpowers/specs/2026-03-24-engram-web-ui-design.md` for required backend API enhancements.
```

- [ ] **Step 7: Verify dev server starts**

```bash
cd web && npm run dev
# Visit http://localhost:3000 — should show "Engram" title
```

- [ ] **Step 8: Commit**

```bash
git add web/ && git commit -m "feat(web): Next.js + Mantine scaffold with CLAUDE.md"
```

---

## Task 2: CORS + API Client + Auth

**Files:**
- Modify: `src/engram/main.py` (add CORS)
- Create: `web/lib/api.ts`
- Create: `web/lib/auth.ts`
- Create: `web/lib/types.ts`
- Create: `web/hooks/useApi.ts`
- Create: `web/hooks/useAuth.ts`
- Create: `web/app/auth/page.tsx`

- [ ] **Step 1: Add CORS middleware to FastAPI**

In `src/engram/main.py`, add after `app = FastAPI(...)`:
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

- [ ] **Step 2: Create TypeScript types**

`web/lib/types.ts` — define interfaces matching all API responses:
```typescript
export interface Memory {
  id: string;
  content: string;
  intent: string | null;
  meaning: string | null;
  interaction_context: string | null;
  source: string;
  source_ref: string;
  authorship: string;
  importance_score: number | null;
  confidence: number;
  reinforcement_count: number;
  status: string;
  visibility: string;
  timestamp: string | null;
  topics: string[];
  people: string[];
}

export interface Belief {
  id: string;
  topic: string;
  stance: string;
  nuance: string | null;
  confidence: number;
  source: string;
  valid_from: string | null;
  valid_until: string | null;
}

export interface Preference {
  id: string;
  category: string;
  value: string;
  strength: number;
  source: string;
}

export interface StyleProfile {
  tone: string | null;
  humor_level: number | null;
  verbosity: number | null;
  formality: number | null;
  vocabulary_notes: string | null;
  communication_patterns: string | null;
}

export interface Profile {
  id: string;
  name: string;
  description: string | null;
}

export interface EngramResponse {
  answer: string;
  confidence: number;
  memory_refs: string[] | null;
  belief_refs: string[] | null;
  caveats: string[];
}

export interface MemoryStats {
  total_memories: number;
  by_source: Record<string, number>;
  topic_count: number;
  person_count: number;
}

export interface Topic {
  topic: string;
  memory_count: number;
}

export interface Person {
  id: string;
  name: string;
  relationship_type: string | null;
  platforms: string[];
  message_count: number;
  interaction_score: number;
  connected_since: string | null;
}

export interface Snapshot {
  id: string;
  label: string | null;
  created_at: string;
  snapshot_data?: Record<string, unknown>;
}
```

- [ ] **Step 3: Create API client**

`web/lib/api.ts`:
```typescript
import { getToken, clearToken } from './auth';

const API_BASE = 'http://localhost:8000';

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!headers['Content-Type'] && options.body && typeof options.body === 'string') {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined') window.location.href = '/auth';
    throw new Error('Unauthorized');
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' }),
};
```

- [ ] **Step 4: Create auth helpers**

`web/lib/auth.ts`:
```typescript
const TOKEN_KEY = 'engram_token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
```

- [ ] **Step 5: Create useApi hook (SWR)**

`web/hooks/useApi.ts`:
```typescript
import useSWR from 'swr';
import { api } from '@/lib/api';

export function useApi<T>(path: string | null) {
  return useSWR<T>(path, (url) => api.get<T>(url));
}
```

- [ ] **Step 6: Create useAuth hook**

`web/hooks/useAuth.ts`:
```typescript
'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated } from '@/lib/auth';

export function useAuth() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/auth');
    } else {
      setReady(true);
    }
  }, [router]);

  return { ready };
}
```

- [ ] **Step 7: Create auth page**

`web/app/auth/page.tsx`:
```tsx
'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Container, Title, Text, TextInput, Button, Alert, Stack, Paper } from '@mantine/core';
import { setToken } from '@/lib/auth';
import { api } from '@/lib/api';
import type { Profile } from '@/lib/types';

export default function AuthPage() {
  const [token, setTokenValue] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleConnect() {
    setLoading(true);
    setError('');
    setToken(token);
    try {
      await api.get<Profile>('/api/identity/profile');
      router.push('/');
    } catch {
      setError('Invalid token. Check your token and try again.');
      localStorage.removeItem('engram_token');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Container size="xs" py={100}>
      <Paper p="xl" radius="md" withBorder>
        <Stack>
          <Title order={2}>Connect to Engram</Title>
          <Text c="dimmed" size="sm">
            Enter your engram owner token. Generate one with: <code>uv run engram init</code>
          </Text>
          {error && <Alert color="red">{error}</Alert>}
          <TextInput
            label="Owner Token"
            placeholder="engram_..."
            value={token}
            onChange={(e) => setTokenValue(e.currentTarget.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
          />
          <Button onClick={handleConnect} loading={loading} fullWidth>
            Connect
          </Button>
        </Stack>
      </Paper>
    </Container>
  );
}
```

- [ ] **Step 8: Verify auth flow**

Start backend (`uv run engram server`) and frontend (`cd web && npm run dev`).
Visit `http://localhost:3000` → should redirect to `/auth`.
Enter token → should redirect to `/` on success.

- [ ] **Step 9: Commit**

```bash
git add src/engram/main.py web/ && git commit -m "feat(web): auth flow, API client, CORS middleware"
```

---

## Task 3: App Shell + Sidebar Navigation

**Files:**
- Create: `web/components/layout/AppShell.tsx`
- Create: `web/components/layout/Sidebar.tsx`
- Modify: `web/app/layout.tsx` (wrap with AppShell)
- Create placeholder pages for all routes

- [ ] **Step 1: Create Sidebar component**

`web/components/layout/Sidebar.tsx` — Mantine NavLink items for all 6 sections + settings. Active link highlighted based on `usePathname()`.

- [ ] **Step 2: Create AppShell wrapper**

`web/components/layout/AppShell.tsx` — Mantine AppShell with navbar (sidebar) and main content area. Handles auth check via `useAuth()`.

- [ ] **Step 3: Update root layout**

Wrap children in the AppShell component. Auth page excluded from AppShell (no sidebar on login).

- [ ] **Step 4: Create placeholder pages**

Create minimal pages for: `/chat`, `/memories`, `/memories/[id]`, `/identity`, `/people`, `/people/[id]`, `/data`, `/settings`. Each just shows a `<Title>` with the page name.

- [ ] **Step 5: Verify navigation**

All sidebar links work, active state highlights correctly, auth redirects work.

- [ ] **Step 6: Commit**

```bash
git add web/ && git commit -m "feat(web): app shell with sidebar navigation"
```

---

## Task 4: Shared Components

**Files:**
- Create: `web/components/common/SourceIcon.tsx`
- Create: `web/components/common/ConfidenceBar.tsx`
- Create: `web/components/common/TopicTag.tsx`
- Create: `web/components/common/PersonChip.tsx`

- [ ] **Step 1: SourceIcon** — renders platform icon/emoji based on source string (gmail→📧, reddit→💬, facebook→📘, instagram→📸, file→📄).

- [ ] **Step 2: ConfidenceBar** — Mantine Progress component, color scales from red (0) to green (1).

- [ ] **Step 3: TopicTag** — Mantine Badge, clickable, links to `/memories?topic=<name>`.

- [ ] **Step 4: PersonChip** — Mantine Badge with avatar, clickable, links to `/people/<id>`.

- [ ] **Step 5: Commit**

```bash
git add web/ && git commit -m "feat(web): shared components (SourceIcon, ConfidenceBar, TopicTag, PersonChip)"
```

---

## Task 5: Dashboard Page

**Files:**
- Modify: `web/app/page.tsx`
- Create: `web/components/chat/ChatInput.tsx` (reused on dashboard)

- [ ] **Step 1: Stats cards row**

Four Mantine Paper cards showing total memories, people, active beliefs, topics. Data from `GET /api/memories/stats` (memories, topics, people) + `GET /api/identity/beliefs` (client-side count for beliefs).

- [ ] **Step 2: Source breakdown donut chart**

Mantine DonutChart from `by_source` stats data.

- [ ] **Step 3: Recent memories list**

Left column: last 10 memories from `GET /api/memories?limit=10`. Each shows SourceIcon, timestamp, content snippet.

- [ ] **Step 4: Quick chat widget**

Right column: compact chat. TextInput + submit. Calls `POST /api/engram/ask`, shows response inline. "Open full chat →" link.

- [ ] **Step 5: Commit**

```bash
git add web/ && git commit -m "feat(web): dashboard with stats, chart, recent memories, quick chat"
```

---

## Task 6: Chat Page

**Files:**
- Create: `web/app/chat/page.tsx`
- Create: `web/components/chat/MessageList.tsx`
- Create: `web/components/chat/ChatInput.tsx` (if not already created)
- Create: `web/components/chat/SourceCitations.tsx`

- [ ] **Step 1: Message list** — scrollable, auto-scroll to bottom. User messages right-aligned (blue), engram responses left-aligned (dark card).

- [ ] **Step 2: Chat input** — TextInput with send button + optional Mantine DatePickerInput for `as_of_date`. Conversation stored in React state (+ localStorage for persistence).

- [ ] **Step 3: Source citations** — expandable Accordion in engram responses showing memory_refs (linked to `/memories/<id>`) and belief_refs.

- [ ] **Step 4: Suggested questions** — shown when conversation is empty. Based on `GET /api/engram/topics` (top 5).

- [ ] **Step 5: Loading states** — skeleton while waiting for response, confidence badge + caveats on each response.

- [ ] **Step 6: Commit**

```bash
git add web/ && git commit -m "feat(web): chat page with citations and as-of-date"
```

---

## Task 7: Backend — Enhanced Memory Search

**Files:**
- Modify: `src/engram/api/routes/memories.py`
- Modify: `src/engram/memory/repository.py`
- Create: `tests/test_api/test_memories_enhanced.py`

- [ ] **Step 1: Add query params to GET /api/memories**

Add: `visibility`, `sort` (date/importance/reinforcement), `date_from`, `date_to`, `offset`, allow comma-separated `sources`.

- [ ] **Step 2: Update repository search()**

Pass through new filters. Add `ORDER BY` support for sort param. Add `OFFSET` for pagination.

- [ ] **Step 3: Add interaction_context to memory detail response**

Ensure `GET /api/memories/{id}` returns `interaction_context` field.

- [ ] **Step 4: Write tests**

Test each new filter param, sort order, pagination.

- [ ] **Step 5: Commit**

```bash
git add src/ tests/ && git commit -m "feat(api): enhanced memory search filters, sort, pagination"
```

---

## Task 8: Memories Page

**Files:**
- Create: `web/app/memories/page.tsx`
- Create: `web/app/memories/[id]/page.tsx`
- Create: `web/components/memories/MemoryCard.tsx`
- Create: `web/components/memories/MemoryFilters.tsx`
- Create: `web/components/memories/MemoryActions.tsx`

- [ ] **Step 1: Filter bar** — Mantine Select for source (multi), TextInput for search, DatePickerInput for range, SegmentedControl for visibility, Select for sort.

- [ ] **Step 2: Memory card list** — paginated with "Load more" button. Each card: SourceIcon, timestamp, content (truncated via Mantine Spoiler), intent badge, ConfidenceBar, TopicTags, PersonChips.

- [ ] **Step 3: Memory detail page** — full memory view at `/memories/[id]`. All fields, evolution chain (parent/child links), topics, people.

- [ ] **Step 4: Memory actions** — inline edit (content, visibility, importance via Mantine modals). Reinforce/Degrade/Evolve buttons with modal for evidence input. Delete with confirmation.

- [ ] **Step 5: Stats bar** — total count + mini donut at top of page.

- [ ] **Step 6: Commit**

```bash
git add web/ && git commit -m "feat(web): memories page with search, filters, edit, actions"
```

---

## Task 9: Identity Page

**Files:**
- Create: `web/app/identity/page.tsx`
- Create: `web/components/identity/BeliefCard.tsx`
- Create: `web/components/identity/PreferenceCard.tsx`
- Create: `web/components/identity/StyleGauges.tsx`
- Create: `web/components/identity/BeliefTimeline.tsx`

- [ ] **Step 1: Tabs layout** — Mantine Tabs: Beliefs | Preferences | Style | Snapshots.

- [ ] **Step 2: Beliefs tab** — belief timeline chart (Mantine LineChart, data from `GET /api/identity/timeline?topic=`), "Run Inference" button, belief card list with CRUD.

- [ ] **Step 3: Preferences tab** — card list grouped by category, CRUD actions.

- [ ] **Step 4: Style tab** — Mantine Slider components for humor/verbosity/formality (0-1), text display for tone, editable Textarea for vocabulary_notes and communication_patterns.

- [ ] **Step 5: Snapshots tab** — table of snapshots, click to view JSON, "Take Snapshot" button, compare mode (client-side diff).

- [ ] **Step 6: Commit**

```bash
git add web/ && git commit -m "feat(web): identity page with beliefs, preferences, style, snapshots, timeline chart"
```

---

## Task 10: Backend — People API

**Files:**
- Create: `src/engram/api/routes/people.py`
- Modify: `src/engram/api/routes/__init__.py`
- Create: `tests/test_api/test_people.py`

- [ ] **Step 1: Create people router**

```
GET  /api/people?q=&sort=&limit=&offset=   — list people with relationship data (join relationships table)
GET  /api/people/{id}                        — person detail with stats
PUT  /api/people/{id}                        — edit relationship_type, name
GET  /api/people/{id}/memories               — memories involving this person
GET  /api/people/graph                       — nodes + edges for D3 (people as nodes, edge weight = interaction_score)
```

- [ ] **Step 2: Register router in __init__.py**

- [ ] **Step 3: Write tests**

Test list, search, detail, edit, memories, graph format.

- [ ] **Step 4: Also add person filter to photos**

`GET /api/photos?person_id=` — filter via photo_people join.

- [ ] **Step 5: Commit**

```bash
git add src/ tests/ && git commit -m "feat(api): people API with search, detail, graph, photo filter"
```

---

## Task 11: People Page + D3 Graph

**Files:**
- Create: `web/app/people/page.tsx`
- Create: `web/app/people/[id]/page.tsx`
- Create: `web/components/people/PeopleTable.tsx`
- Create: `web/components/people/PersonDetail.tsx`
- Create: `web/components/people/RelationshipGraph.tsx`

- [ ] **Step 1: List view tab** — Mantine Table with search, sortable columns (name, relationship, platform, messages, interaction score, connected since). Click row → navigate to detail page.

- [ ] **Step 2: Person detail page** — name, relationship type (editable), platform badges, stats, memories list (from `/api/people/{id}/memories`), photos, common topics.

- [ ] **Step 3: Graph view tab** — D3 force-directed graph. `GET /api/people/graph` returns `{nodes: [{id, name, score, platform}], edges: [{source, target, weight}]}`. Render with D3 in a `useRef` canvas. Click node → navigate to person detail.

- [ ] **Step 4: Graph controls** — minimum score slider, platform filter toggles, zoom buttons.

- [ ] **Step 5: Commit**

```bash
git add web/ && git commit -m "feat(web): people page with list, D3 relationship graph, person detail"
```

---

## Task 12: Backend — Jobs List + Export Validation

**Files:**
- Modify: `src/engram/api/routes/ingest.py`
- Modify: `src/engram/ingestion/service.py`

- [ ] **Step 1: Add jobs list endpoint**

`GET /api/ingest/jobs?limit=20&status=` — list all ingestion jobs, newest first.

- [ ] **Step 2: Add export validation endpoint**

`POST /api/ingest/export/validate` — accepts `{platform, export_path}`, runs the parser's `validate()` method, returns `{valid, platform, details}`.

- [ ] **Step 3: Tests**

- [ ] **Step 4: Commit**

```bash
git add src/ tests/ && git commit -m "feat(api): ingestion jobs list and export validation endpoints"
```

---

## Task 13: Data Management Page

**Files:**
- Create: `web/app/data/page.tsx`
- Create: `web/components/data/PlatformCard.tsx`
- Create: `web/components/data/JobsTable.tsx`
- Create: `web/components/data/SourceManager.tsx`

- [ ] **Step 1: Platform import cards** — grid of cards for Gmail, Reddit, Facebook, Instagram, File. Each shows status, memory count. "Import" button opens modal with path input, validate button, platform instructions (Mantine Accordion), register button.

- [ ] **Step 2: File upload** — Mantine Dropzone for direct file upload (`POST /api/ingest/file`).

- [ ] **Step 3: Jobs table** — auto-refreshing table from `GET /api/ingest/jobs`. Status badges, progress indicators.

- [ ] **Step 4: Source visibility manager** — table from `GET /api/sources`. Bulk visibility toggles via `POST /api/sources/bulk`.

- [ ] **Step 5: Commit**

```bash
git add web/ && git commit -m "feat(web): data management page with import, jobs, source visibility"
```

---

## Task 14: Settings Page

**Files:**
- Create: `web/app/settings/page.tsx`

- [ ] **Step 1: API keys section** — redacted display from `GET /api/config`, update form.

- [ ] **Step 2: Token management** — list tokens from `GET /api/tokens`, create new (show once in modal), revoke.

- [ ] **Step 3: Export/Import** — "Export Engram" button (downloads JSON from `POST /api/engram/export`), "Import Engram" file upload.

- [ ] **Step 4: Commit**

```bash
git add web/ && git commit -m "feat(web): settings page with tokens, keys, export/import"
```

---

## Summary

14 tasks building up incrementally:
1. Next.js scaffold + CLAUDE.md
2. CORS + API client + auth flow
3. App shell + sidebar navigation
4. Shared components
5. Dashboard page
6. Chat page
7. Backend: enhanced memory search
8. Memories page
9. Identity page
10. Backend: people API
11. People page + D3 graph
12. Backend: jobs list + export validation
13. Data management page
14. Settings page

Each task produces working, testable code with a commit. Backend enhancements (tasks 7, 10, 12) are positioned immediately before the frontend page that needs them.
