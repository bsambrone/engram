# Engram — Design & Architecture

## Vision

Engram is a self-hosted digital engram — a realistic digital representation of a person built from their real data. Inspired by the engram concept from Cyberpunk 2077 but grounded in current LLM technology.

The engram is not a chatbot. It's a structured representation of who someone is, what they believe, how they communicate, and how they've changed over time. It ingests a person's "digital exhaust" (emails, social media, messages, photos), uses LLMs to extract intent and meaning from every piece of data, builds a living memory system that evolves, infers identity traits, and exposes the result via API and MCP server so agents or humans can interact with it.

When you ask the engram a question, it responds as that person would — grounded in real memories and beliefs, not hallucinated personality.

## Core Concepts

### Living Memories
Memories are not static records. They strengthen when reinforced by new data, weaken when contradicted, and evolve when nuance is discovered. A memory that said "I hate remote work" in 2020 might evolve to "I prefer remote work for deep focus but miss in-person collaboration" by 2024. Both versions are preserved with temporal tracking.

### Identity Inference
The system analyzes memories to infer beliefs, preferences, and communication style. These traits have confidence scores and temporal bounds — the system knows when a belief first appeared, how it changed, and whether the user has manually overridden it. User-set identity traits are never overwritten by inference.

### Temporal Awareness
Everything has a time dimension. You can ask the engram "what did I think about X in 2023?" and get an accurate answer using only data from before that date. Beliefs have `valid_from`/`valid_until` fields. Identity snapshots capture point-in-time state for visualization.

### Privacy by Design
All data stays local. Owner access shows full citations (which email, which Reddit post). Shared access (for others querying your engram) shows only the response — no sources, no memory IDs, no private data.

## Architecture

```
Data Exports → Parsers → Processing Pipeline → Memory Store → Identity Layer → RAG Engine → MCP/REST API
```

### Data Flow

1. **Export Parsers** read platform data exports (Gmail MBOX, Reddit CSV, Facebook/Instagram JSON)
2. **Processing Pipeline** transforms raw text: normalize → chunk → embed (OpenAI) → LLM analyze (extract intent, meaning, topics, people, locations, life events)
3. **Memory Store** persists memories with vector embeddings, linked to topics, people, and relationships
4. **Identity Layer** infers beliefs, preferences, and style from the memory corpus
5. **RAG Engine** assembles context (memories + identity) into prompts that make the LLM respond as the person
6. **MCP/REST API** exposes the engram to clients (Claude Desktop, Claude Code, web apps, agents)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| Framework | FastAPI (async) |
| Package manager | uv |
| Database | PostgreSQL 16 + pgvector (Docker, port 5433) |
| Cache/Queue | Redis (Docker, port 6379) |
| ORM/Migrations | SQLAlchemy (async/asyncpg) + Alembic |
| LLM Generation | OpenAI API (configurable model, default gpt-5.2) |
| Embeddings | OpenAI text-embedding-3-small (1536 dimensions) |
| Image Analysis | OpenAI gpt-4o (vision) |
| Image Generation | OpenAI gpt-image-1 |
| MCP | MCP Python SDK (stdio transport) |
| Testing | pytest (310+ tests) |
| Linting | ruff |

Anthropic/Claude API support is architecturally planned but deferred. Currently OpenAI handles both generation and embeddings.

## File Structure

```
engram/
├── src/engram/
│   ├── __init__.py                    # Package version
│   ├── main.py                        # FastAPI app entry point
│   ├── cli.py                         # Click CLI: init, server, mcp, ingest, status
│   ├── config.py                      # Pydantic BaseSettings (reads .env)
│   ├── db.py                          # Async SQLAlchemy engine + session factory
│   ├── encryption.py                  # Fernet encrypt/decrypt helpers
│   │
│   ├── models/                        # SQLAlchemy ORM models
│   │   ├── base.py                    # DeclarativeBase, UUIDMixin, TimestampMixin
│   │   ├── memory.py                  # Memory, Topic, Person, join tables
│   │   ├── identity.py               # IdentityProfile, Belief, Preference, StyleProfile, Snapshot
│   │   ├── connector.py              # DataExport, IngestionJob
│   │   ├── auth.py                   # AccessToken
│   │   ├── photo.py                  # Photo, PhotoPerson
│   │   └── social.py                 # Relationship, Location, LifeEvent
│   │
│   ├── ingestion/
│   │   ├── service.py                # Job management, export registration
│   │   └── parsers/
│   │       ├── base.py               # ExportParser protocol, RawDocument dataclass
│   │       ├── file.py               # FileParser (txt/md/json)
│   │       ├── gmail.py              # GmailExportParser (MBOX via mailbox stdlib)
│   │       ├── reddit.py             # RedditExportParser (CSV)
│   │       ├── facebook.py           # FacebookExportParser (JSON with encoding fix)
│   │       └── instagram.py          # InstagramExportParser (JSON with encoding fix)
│   │
│   ├── processing/
│   │   ├── pipeline.py               # Full orchestrator: normalize → chunk → embed → analyze → store
│   │   ├── normalizer.py             # HTML stripping, whitespace normalization
│   │   ├── chunker.py                # Sentence-aware chunking with overlap (tiktoken)
│   │   ├── embedder.py               # OpenAI embeddings with Redis cache (30-day TTL)
│   │   └── analyzer.py               # LLM-powered intent/meaning/people/location extraction
│   │
│   ├── memory/
│   │   ├── repository.py             # CRUD, vector search with composite ranking, topic/person linking
│   │   └── service.py                # store, remember, reinforce, degrade, evolve, stats
│   │
│   ├── identity/
│   │   ├── repository.py             # CRUD for beliefs, preferences, style, snapshots (temporal)
│   │   ├── service.py                # Full identity retrieval, snapshots, temporal queries
│   │   └── inference.py              # LLM-powered trait extraction with evolve pattern + auto-snapshot
│   │
│   ├── llm/
│   │   ├── providers.py              # OpenAI generation wrapper with retry
│   │   └── rag.py                    # RAG pipeline: embed → search → identity → prompt → generate
│   │
│   ├── photos/
│   │   ├── repository.py             # Photo CRUD
│   │   └── service.py                # Upload, vision analysis (intent/meaning/people), image generation
│   │
│   ├── api/
│   │   ├── deps.py                   # Auth dependencies: get_current_token, require_owner
│   │   └── routes/
│   │       ├── tokens.py             # POST/GET/DELETE /api/tokens
│   │       ├── config_routes.py      # GET/PUT /api/config
│   │       ├── ingest.py             # POST /api/ingest/file, /export; GET /status, /exports
│   │       ├── memories.py           # CRUD + search + stats + timeline + contradictions
│   │       ├── sources.py            # Visibility management (active/private/excluded)
│   │       ├── identity.py           # Beliefs/preferences/style CRUD, inference, snapshots, timeline
│   │       ├── engram.py             # ask, topics, opinions, summarize, simulate, compare, imagine, export/import
│   │       └── photos.py             # Upload, list, update, delete
│   │
│   └── mcp/
│       └── server.py                 # MCP server with 9 tools (answer_as_self, search_memories, etc.)
│
├── tests/                            # 310+ tests (unit, API, integration)
├── scripts/                          # Ingestion and import scripts
├── alembic/                          # Database migrations (additive only!)
├── docs/superpowers/                 # Design specs and implementation plans
├── docker-compose.yml                # pgvector + Redis
├── pyproject.toml                    # uv config, dependencies
└── .env                              # API keys, DB URL (gitignored)
```

## Database Schema

### Core Memory System
- **memories** — Content with pgvector embeddings, LLM-extracted intent/meaning/interaction_context, authorship tracking, importance/confidence scores, reinforcement counts, visibility (active/private/excluded), status (active/degraded/evolved), temporal timestamps
- **topics** — Unique topic names extracted from memories
- **memory_topics** — M2M join: which memories mention which topics
- **people** — Named individuals mentioned in or associated with memories
- **memory_people** — M2M join: which memories involve which people

### Identity System
- **identity_profiles** — User profile (name, description). Usually one per engram.
- **beliefs** — Inferred or user-set beliefs with topic, stance, nuance, confidence. **Temporal**: `valid_from`/`valid_until` track evolution. Archived beliefs (valid_until != NULL) preserve history.
- **preferences** — Category/value pairs with strength. Also temporal.
- **style_profiles** — Communication style: tone, humor, verbosity, formality, vocabulary notes, patterns. One per profile (UNIQUE). Also temporal.
- **identity_snapshots** — Point-in-time JSONB captures of full identity state. Auto-created after inference.
- **belief_memories** / **preference_memories** — M2M joins linking traits to supporting memories

### Social Graph
- **relationships** — Tracks connections between the user and people, per platform. Includes connected_since, message_count, interaction_score, relationship_type (friend/contact/family/tagged_together).
- **locations** — Places mentioned or visited, with visit counts and first/last visited dates.
- **life_events** — Significant events (social, milestones, travel) with dates and associated people.

### Photos
- **photos** — Image files with metadata, descriptions, tags. `is_reference=True` marks photos of the user (for image generation).
- **photo_people** — M2M join: who appears in which photos.

### Infrastructure
- **access_tokens** — Bearer tokens with owner/shared access levels, expiry, revocation.
- **data_exports** — Registered platform data export paths and processing status.
- **ingestion_jobs** — Background job tracking for data processing.

## Processing Pipeline Detail

When a document enters the pipeline:

1. **Normalize** — Strip HTML, decode entities, collapse whitespace
2. **Chunk** — Split into ~500-token segments with 50-token overlap (sentence-aware)
3. **Embed** — OpenAI text-embedding-3-small → 1536-dim vector, cached in Redis
4. **Analyze** — LLM extracts:
   - `intent` — Why was this written? (express opinion, ask question, share news, etc.)
   - `meaning` — What does this reveal about the person's beliefs, values, preferences?
   - `topics` — Key topics mentioned
   - `people` — People mentioned by name (@mentions, natural language)
   - `locations` — Places mentioned
   - `life_events` — Significant events detected
   - `importance_score` — 0.0-1.0 identity relevance
   - `keep` — Should this memory be stored? (filters out trivial non-user content)
   - `interaction_context` — For received content: how did this shape the user's position?
5. **Store** — Memory record with embedding, linked topics/people. Also updates relationships table, locations table, life_events table.
6. **Photo cross-reference** — If the document has associated images, upload and link them.

### Memory Search Ranking

Vector search uses a composite formula, not just cosine distance:
```
score = cosine_similarity * 0.5 + importance_score * 0.2 + recency_score * 0.2 + reinforcement_score * 0.1
```
Recency uses exponential decay with configurable half-life (default 365 days).

## Data Sources

Engram processes offline data exports, not live APIs. Users download their data from each platform:

| Platform | Export Format | Parser | Key Content |
|----------|-------------|--------|-------------|
| Gmail | Google Takeout MBOX | `gmail.py` | Emails (sent=user_authored, received) |
| Reddit | Data Request CSV | `reddit.py` | Posts, comments, chat history |
| Facebook | Download Your Information JSON | `facebook.py` | Posts, comments, messages, friends, events |
| Instagram | Download Your Data JSON | `instagram.py` | Posts, comments, messages, photos |
| Files | Direct upload (txt/md/json) | `file.py` | Any text content |

### Free signals (no LLM cost)
Each platform export also contains structured data imported directly:
- Reddit: subscribed subreddits → topics
- Instagram: interest categories, locations, close friends, synced contacts, profile photo
- Facebook: friends list, events, AI interests, pages followed, groups, message partners

## Identity Inference

The inference engine (`identity/inference.py`):
1. Queries the 50 highest-importance user-authored memories
2. Asks the LLM to extract beliefs, preferences, and communication style
3. Uses an **evolve pattern** for existing beliefs: if the stance changed, archive the old version (set `valid_until=now`) and create a new one (set `valid_from=now`). If only confidence changed, update in place.
4. Never overwrites `source="user"` traits (manual overrides are sacred)
5. Auto-snapshots the full identity state after each inference run

## RAG Pipeline

When someone asks the engram a question:
1. Embed the query with OpenAI
2. Vector search memories (composite ranking, filtered by visibility and optional `as_of_date`)
3. Fetch identity context (beliefs, preferences, style — also filtered by as_of_date if provided)
4. Assemble a system prompt: "You are {name}'s engram..." with identity traits and relevant memories
5. Generate response via OpenAI
6. Return with confidence score, memory refs (owner only), belief refs (owner only), caveats

The `as_of_date` parameter enables temporal queries: "What did I think about remote work in 2023?"

## MCP Server

The MCP server exposes 9 tools for Claude Desktop/Claude Code:
- `answer_as_self` — Ask the engram a question
- `list_topics` — Topics the engram knows about
- `summarize_self` — Narrative identity summary
- `simulate_decision` — How would this person decide?
- `get_beliefs` — List beliefs by topic
- `get_opinions` — Opinions with nuance
- `search_memories` — Semantic memory search
- `recall_about` — Everything about a person/topic
- `compare_perspectives` — Compare views with another stance

All MCP tools use shared access (no citations) by default.

## CLI

```bash
engram init        # Interactive setup wizard (Docker, API keys, profile, data exports)
engram server      # Start FastAPI REST API
engram mcp         # Start MCP server (stdio)
engram ingest      # Process registered data exports
engram status      # Show engram statistics
```

## Key Design Decisions

1. **Data exports, not live APIs** — Platform APIs are restrictive. Data exports give complete access to the user's own data.
2. **OpenAI for everything** — Single API key for embeddings + generation. Anthropic support planned but deferred.
3. **Temporal identity** — Beliefs evolve. The engram tracks when and how you changed.
4. **Living memories** — Reinforcement, degradation, evolution. Memories are not static.
5. **Owner vs shared access** — Full transparency for the owner, privacy for shared access.
6. **Additive migrations only** — The database has real user data. Never drop tables.
7. **LLM-extracted meaning, not just RAG** — Every piece of data gets intent and meaning analysis. The engram understands why you said something, not just what you said.
8. **Monolith-first** — Simple deployment, shared services. Can extract modules later.

## Current State (March 2026)

- **10,700+ memories** across Gmail (6,332), Facebook (3,700+), Reddit (558), Instagram (99)
- **35,000+ topics**, **2,500+ people**, **625+ relationships**
- **21 active beliefs** with temporal evolution history
- **45+ preferences** (inferred + platform-derived)
- **57 photos** (1 reference, 16 Instagram with vision analysis, 40 Facebook)
- **24 life events** from Facebook
- **2 identity snapshots**
- **310+ automated tests**
- MCP server with 9 tools
- Interactive setup wizard with platform data export guidance

## Roadmap

### Near-term
- Web UI for memory/identity management and visualization
- Timeline visualization of belief evolution
- Periodic scheduled inference (re-analyze as new data arrives)
- Facebook photo vision analysis batch processing
- Deduplication of similar/overlapping memories

### Medium-term
- Voice synthesis (speak as the person)
- Additional export parsers (Twitter/X, Discord, Slack, LinkedIn)
- Continuous learning (watch for new data exports)
- Multi-device MCP deployment
- Relationship graph visualization

### Long-term
- Video avatars
- Multi-agent identities (different personas)
- Real-time conversational mode
- Federated engram sharing
- Mobile app
