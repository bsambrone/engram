# MCP Behavior Configuration + Enhanced Export/Import — Design Specification

## Overview

Two features that work together:

1. **MCP Behavior Profiles** — Configurable rules that control how the MCP server responds (response mode, base model augmentation, persona, topic restrictions, privacy tiers). Stored in DB, editable via web UI.
2. **Enhanced Export/Import** — Selective export with configurable data inclusion, dedicated UI page, merge/replace import, MCP profile always bundled.

---

## MCP Behavior System

### Database: `mcp_profiles` table

```
mcp_profiles
├── id: UUID (primary key)
├── name: String(200) — e.g. "default", "public", "work-restricted"
├── is_active: Boolean — one active profile at a time
├── response_mode: String(50) — "full_rag" or "beliefs_only"
├── augment_with_base_model: Boolean — true = LLM fills gaps, false = "I don't know"
├── persona_mode: String(50) — "in_character" or "factual"
├── restricted_topics: ARRAY(String) — topics to refuse
├── privacy_tier: String(50) — "full", "no_sources", "beliefs_only"
├── created_at: DateTime
├── updated_at: DateTime
```

### Behavior Rules

**response_mode:**
- `full_rag` (default) — current behavior: embed query → search memories → fetch identity → assemble prompt → generate
- `beliefs_only` — skip memory search entirely. Only use beliefs, preferences, and style to respond. Faster, more deterministic, but shallow.

**augment_with_base_model:**
- `true` (default) — current behavior. The LLM can use its general knowledge to fill gaps.
- `false` — the system prompt includes: "If the engram data doesn't contain information about this topic, respond with 'I don't have information about that.' Do NOT use your general knowledge to fill gaps. Only state things that are supported by the provided memories and beliefs."

**persona_mode:**
- `in_character` (default) — responds as the person: "I think X because..."
- `factual` — responds about the person: "Bill thinks X because his memories show..."

**restricted_topics:**
- Array of topic strings (e.g., ["health", "finances", "work history"])
- Before running RAG, check if the query matches any restricted topic (keyword match against the topic list)
- If matched, respond with: "I'm not configured to discuss that topic."
- Matching is case-insensitive substring match against the query text

**privacy_tier:**
- `full` — owner-level access: citations, memory refs, belief refs in responses
- `no_sources` — current shared behavior: response only, no citations
- `beliefs_only` — only share belief-derived information, no raw memories used at all (equivalent to response_mode=beliefs_only but enforced at the privacy level)

### MCP Server Integration

In `src/engram/mcp/server.py`, before each tool call:
1. Query the active MCP profile from the database
2. Apply behavior rules:
   - Check restricted topics → refuse if matched
   - Set response_mode → pass to ask_engram
   - Set augment_with_base_model → modify system prompt
   - Set persona_mode → modify system prompt
   - Set privacy_tier → control what's returned

### RAG Pipeline Changes

`ask_engram()` in `src/engram/llm/rag.py` needs new parameters:
```python
async def ask_engram(
    session, query, *,
    is_owner=True,
    as_of_date=None,
    response_mode="full_rag",        # NEW
    augment_with_base_model=True,    # NEW
    persona_mode="in_character",     # NEW
    privacy_tier="full",             # NEW
) -> EngramResponse:
```

The `build_prompt()` function adjusts based on these:
- `response_mode="beliefs_only"` → skip memory search, only pass beliefs/preferences/style to prompt
- `augment_with_base_model=False` → add "do not use general knowledge" instruction
- `persona_mode="factual"` → change "You are {name}'s engram" to "You are describing {name}'s engram. Respond in third person about {name}."
- `privacy_tier="beliefs_only"` → don't include memories in prompt, return null for memory_refs

### REST API

```
GET    /api/mcp/profiles              — list all profiles
GET    /api/mcp/profiles/active       — get the active profile
POST   /api/mcp/profiles              — create profile
PUT    /api/mcp/profiles/{id}         — update profile fields
DELETE /api/mcp/profiles/{id}         — delete (cannot delete active)
PUT    /api/mcp/profiles/{id}/activate — set as active (deactivates current)
```

All endpoints are owner-only.

**Create/Update body:**
```json
{
  "name": "public",
  "response_mode": "beliefs_only",
  "augment_with_base_model": false,
  "persona_mode": "in_character",
  "restricted_topics": ["health", "finances"],
  "privacy_tier": "no_sources"
}
```

### Default Profile

During `engram init` or first API access, create a "default" profile:
```json
{
  "name": "default",
  "is_active": true,
  "response_mode": "full_rag",
  "augment_with_base_model": true,
  "persona_mode": "in_character",
  "restricted_topics": [],
  "privacy_tier": "full"
}
```

---

## Enhanced Export/Import

### Export Request

`POST /api/engram/export` updated to accept selective options:

```json
{
  "include": {
    "memories": true,
    "beliefs": true,
    "preferences": true,
    "style": true,
    "photos": false,
    "relationships": true,
    "locations": true,
    "life_events": true
  },
  "memory_sources": ["gmail", "reddit", "facebook", "instagram"],
  "include_photo_data": false
}
```

- `include` — which data types to export (all default to true)
- `memory_sources` — filter memories by source (null = all sources)
- `include_photo_data` — if true, include base64-encoded image data in photos (large!). If false, metadata only.

### Export Format

```json
{
  "version": "2.0",
  "exported_at": "2026-03-28T12:00:00Z",
  "export_options": { ... },
  "profile": { "name": "Bill", "description": "..." },
  "mcp_profile": {
    "name": "default",
    "response_mode": "full_rag",
    "augment_with_base_model": true,
    "persona_mode": "in_character",
    "restricted_topics": [],
    "privacy_tier": "full"
  },
  "memories": [ ... ],
  "beliefs": [ ... ],
  "preferences": [ ... ],
  "style_profile": { ... },
  "photos": [ ... ],
  "relationships": [ ... ],
  "locations": [ ... ],
  "life_events": [ ... ]
}
```

MCP profile is always included regardless of checkbox selection.

Sections omitted from `include` are not present in the JSON (not empty arrays — absent entirely).

### Serialized Shapes for Social Models

**Relationships:**
```json
{
  "person_name": "Lindsay Wise",
  "platform": "instagram",
  "relationship_type": "contact",
  "connected_since": "2024-01-15T00:00:00",
  "message_count": 62,
  "interaction_score": 0.62,
  "notes": null
}
```

**Locations:**
```json
{
  "name": "San Leandro, California",
  "address": null,
  "source": "instagram",
  "visit_count": 3,
  "first_visited": "2023-06-01T00:00:00",
  "last_visited": "2025-11-15T00:00:00"
}
```

**Life Events:**
```json
{
  "title": "Baby Herndon Gender Reveal!!",
  "description": null,
  "event_date": "2020-08-17T00:00:00",
  "source": "facebook",
  "source_ref": "event-12345",
  "event_type": "social",
  "people": "Herndon family"
}
```

### Import Request

`POST /api/engram/import` updated:

```json
{
  "data": { ... },
  "mode": "merge"
}
```

**Merge mode** deduplication per type:
- `memories` — skip if matching `source` + `source_ref` already exists
- `beliefs` — skip if matching `topic` + `stance` exists (same belief)
- `preferences` — skip if matching `category` + `value` exists
- `relationships` — skip if matching `person_name` + `platform` exists (update message_count/score if higher)
- `locations` — skip if matching `name` exists (update visit_count/last_visited if newer)
- `life_events` — skip if matching `title` + `source` exists
- `photos` — skip if matching `source` + `source_ref` exists
- `mcp_profile` — create as a new inactive profile (user can activate via UI)

**Replace mode** — for each data type present in the import:
- Delete ALL records of that type (memories, beliefs, etc. — full table wipe for that type)
- Then insert the imported data
- This is destructive — the UI shows a red warning

Note: Social models (relationships, locations, life_events) are not scoped to a profile_id — they are global. Replace mode deletes all records in the table for that type.

### Export Preview

New endpoint for the UI to show counts before downloading:

```
POST /api/engram/export/preview
```

Same body as export, returns:
```json
{
  "counts": {
    "memories": 6332,
    "beliefs": 24,
    "preferences": 45,
    "style": 1,
    "photos": 103,
    "relationships": 684,
    "locations": 343,
    "life_events": 426
  },
  "estimated_size_mb": 45.2
}
```

---

## Web UI

### New Sidebar Items

Add to sidebar between People and Settings:
- 🔌 MCP Config → `/mcp-config`
- 📤 Export → `/export`

### MCP Configuration Page (`/mcp-config`)

**Profile management:**
- Dropdown to select profile (with active badge)
- "Create New Profile" button → modal with name input
- "Delete Profile" button (disabled for active profile)
- "Set as Active" button

**Settings form (for selected profile):**
- Response Mode: Mantine SegmentedControl (`Full RAG` / `Beliefs Only`)
- Augment with Base Model: Mantine Switch
- Persona Mode: Mantine SegmentedControl (`In Character` / `Factual`)
- Restricted Topics: Mantine TagsInput (type topic, enter to add, click x to remove)
- Privacy Tier: Mantine Select (`Full Access` / `No Source Citations` / `Beliefs Only`)
- Save button

### Export Page (`/export`)

**Two tabs: Export | Import**

**Export tab:**
- Checkboxes (Mantine Checkbox.Group) for data selection:
  - ☑ Memories (with sub-checkboxes for sources: Gmail, Reddit, Facebook, Instagram)
  - ☑ Beliefs
  - ☑ Preferences
  - ☑ Style Profile
  - ☐ Photos (with toggle: metadata only / include images)
  - ☑ Relationships
  - ☑ Locations
  - ☑ Life Events
  - ☑ MCP Profile (always checked, disabled — can't uncheck)
- "Preview" button → calls `/api/engram/export/preview`, shows counts and estimated size
- "Download Export" button → calls `/api/engram/export`, triggers JSON download
- Filename: `engram-{profile_name}-{YYYY-MM-DD}.json`

**Import tab:**
- Mantine Dropzone for JSON file
- After file selected: parse and show preview (counts of each data type in the file)
- Mode selector: Mantine SegmentedControl (`Merge` / `Replace`)
- Warning for Replace mode: "This will delete existing data of the selected types before importing."
- "Import" button → uploads JSON to `/api/engram/import`
- Result summary alert

---

## Backend Files

### New:
- `src/engram/models/mcp_config.py` — McpProfile model
- `src/engram/api/routes/mcp_config.py` — MCP profile CRUD routes
- `tests/test_api/test_mcp_config.py` — MCP profile API tests

### Modified:
- `src/engram/models/__init__.py` — register McpProfile
- `src/engram/api/routes/__init__.py` — register mcp_config router
- `src/engram/mcp/server.py` — read active profile, apply behavior rules
- `src/engram/llm/rag.py` — new params (response_mode, augment, persona, privacy)
- `src/engram/api/routes/engram.py` — update export/import endpoints
- `alembic/versions/` — new additive migration for mcp_profiles table

### Web:
- `web/app/(dashboard)/mcp-config/page.tsx` — MCP configuration page
- `web/app/(dashboard)/export/page.tsx` — Export/Import page
- `web/components/layout/Sidebar.tsx` — add new nav items

---

## Build Order

1. **McpProfile model + migration** — new table, model, migration
2. **MCP Profile API** — CRUD endpoints + tests
3. **RAG pipeline updates** — new params for behavior modes
4. **MCP server integration** — read profile, apply rules, restricted topics check
5. **Enhanced export/import API** — selective export, preview, merge/replace import
6. **MCP Config web page** — profile management UI
7. **Export web page** — selective export/import UI
8. **Sidebar updates** — add new nav items
