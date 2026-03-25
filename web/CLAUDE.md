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

- **Next.js 14+** with App Router (all pages in `app/`)
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
| All page routes | `app/{chat,memories,identity,people,data,settings}/` |

## Auth

Token stored in localStorage (`engram_token`). Every API call reads from localStorage and adds `Authorization: Bearer <token>`. If 401, redirects to `/auth`.

## API

All calls go through `lib/api.ts` which wraps fetch with:
- Base URL: `http://localhost:8000`
- Auto auth header from localStorage
- Typed responses
- 401 → redirect to /auth

## Backend Requirements

The FastAPI backend must have CORS enabled for `http://localhost:3000`. See the spec at `docs/superpowers/specs/2026-03-24-engram-web-ui-design.md` for backend API enhancements.
