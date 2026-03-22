# Engram Platform — Design Specification

## Vision

A programmable, self-hosted digital engram built from a person's real data. Inspired by Cyberpunk 2077's engram concept, grounded in current LLM technology. Ingests digital exhaust (emails, posts, files, photos), builds structured living memories with intent and meaning, infers identity traits, and exposes the engram via MCP server and REST API for agentic use or conversation.

The engram speaks as the person — not a chatbot, but a structured representation of who someone is, what they believe, and how they communicate.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Language | Python |
| Framework | FastAPI (async) |
| Package manager | uv |
| Database | PostgreSQL 16 + pgvector (Docker) |
| Cache/Queue | Redis (Docker) |
| ORM | SQLAlchemy (async, asyncpg) |
| Migrations | Alembic |
| LLM (generation/analysis) | Claude API (Anthropic SDK) |
| Embeddings | OpenAI text-embedding-ada-002 |
| Image generation | OpenAI GPT Image (gpt-image-1) |
| MCP | MCP Python SDK |
| Testing | pytest |
| Linting/Formatting | ruff |
| Auth model | Users bring their own API keys |

---

## Architecture

Monolith-first: single FastAPI application, modular Python packages, shared database and service layer. REST API and MCP server both consume the same services.

```
Data Sources → Ingestion → Processing → Memory Store → Identity Layer → LLM Engine → MCP/REST → Clients
```

---

## Project Structure

```
engram/
├── src/engram/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── cli.py                     # CLI entry point (engram init/server/ingest/status)
│   ├── config.py                  # Pydantic BaseSettings, reads .env
│   ├── db.py                      # Async SQLAlchemy engine/session
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── memory.py              # memories, topics, people, join tables
│   │   ├── identity.py            # profiles, beliefs, preferences, style, snapshots
│   │   ├── connector.py           # connector_configs, ingestion_jobs
│   │   ├── auth.py                # access_tokens
│   │   └── photo.py               # photos
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── service.py             # Ingestion orchestration
│   │   └── connectors/
│   │       ├── __init__.py
│   │       ├── base.py            # Connector protocol + RawDocument
│   │       ├── file.py            # File upload connector
│   │       ├── gmail.py           # Gmail API connector
│   │       └── reddit.py          # Reddit PRAW connector
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── pipeline.py            # Orchestrates normalize → chunk → embed → analyze → store
│   │   ├── normalizer.py          # Strip HTML, clean text
│   │   ├── chunker.py             # Sentence-aware chunking
│   │   ├── embedder.py            # OpenAI embedding client
│   │   └── analyzer.py            # LLM-powered intent/meaning/authorship analysis
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── repository.py          # CRUD + vector search + filtered queries
│   │   └── service.py             # remember, recall, reinforce, degrade, evolve, timeline
│   ├── identity/
│   │   ├── __init__.py
│   │   ├── inference.py           # Auto-infer beliefs/preferences/style from memories
│   │   ├── repository.py          # CRUD for identity tables
│   │   └── service.py             # Identity operations + user overrides + snapshots
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── providers.py           # Claude + OpenAI client wrappers
│   │   └── rag.py                 # RAG pipeline: embed → search → assemble prompt → generate
│   ├── photos/
│   │   ├── __init__.py
│   │   ├── service.py             # Photo management + generation
│   │   └── repository.py          # Photo CRUD
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                # FastAPI dependencies (DB session, auth, access level)
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── ingest.py
│   │       ├── connectors.py
│   │       ├── memories.py
│   │       ├── sources.py
│   │       ├── identity.py
│   │       ├── engram.py
│   │       ├── photos.py
│   │       ├── config.py
│   │       └── tokens.py
│   └── mcp/
│       ├── __init__.py
│       └── server.py              # MCP server exposing tools
├── tests/
│   ├── conftest.py                # Shared fixtures (test DB, async client)
│   ├── test_ingestion/
│   ├── test_processing/
│   ├── test_memory/
│   ├── test_identity/
│   ├── test_llm/
│   ├── test_api/
│   ├── test_mcp/
│   └── test_photos/
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── docker-compose.yml             # pgvector + Redis
├── pyproject.toml                 # uv config, dependencies, ruff config
├── README.md
├── .gitignore
└── .env.example
```

---

## Data Models

### Memory System

#### memories

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| parent_memory_id | UUID (FK, nullable) | Evolution chain — points to parent memory |
| content | Text | Original content |
| embedding | Vector(1536) | OpenAI ada-002 embedding |
| intent | Text | LLM-extracted: why was this said/written |
| meaning | Text | LLM-extracted: what this reveals about the person |
| timestamp | DateTime | When the original content was created |
| source | String | "file", "gmail", "reddit" |
| source_ref | String | Original filename, message ID, permalink |
| authorship | String | "user_authored", "received", "other_reply" |
| importance_score | Float | 0.0–1.0, increases with reinforcement |
| confidence | Float | 0.0–1.0, decreases on contradiction |
| reinforcement_count | Integer | Times supported by new data |
| last_reinforced_at | DateTime | |
| visibility | String | "active", "private", "excluded" |
| status | String | "active", "degraded", "evolved", "archived" |
| created_at | DateTime | |
| updated_at | DateTime | |

#### topics

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| name | String | Unique |
| created_at | DateTime | |

#### memory_topics

| Column | Type |
|--------|------|
| memory_id | UUID (FK) |
| topic_id | UUID (FK) |

#### people

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| name | String | |
| relationship | String | e.g. "friend", "coworker", "family" |
| created_at | DateTime | |

#### memory_people

| Column | Type |
|--------|------|
| memory_id | UUID (FK) |
| person_id | UUID (FK) |

### Identity System

#### identity_profiles

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| name | String | e.g. "default" |
| description | Text | |
| created_at | DateTime | |
| updated_at | DateTime | |

#### beliefs

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| profile_id | UUID (FK) | |
| topic | String | |
| stance | Text | |
| nuance | Text (nullable) | Caveats, exceptions, context |
| confidence | Float | 0.0–1.0 |
| source | String | "inferred" or "user" |
| first_seen | DateTime | When this belief first appeared |
| last_updated | DateTime | |
| created_at | DateTime | |
| updated_at | DateTime | |

#### belief_memories (join table)

| Column | Type |
|--------|------|
| belief_id | UUID (FK, cascade delete) |
| memory_id | UUID (FK, cascade delete) |

#### preferences

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| profile_id | UUID (FK) | |
| category | String | |
| value | Text | |
| strength | Float | 0.0–1.0 |
| source | String | "inferred" or "user" |
| created_at | DateTime | |
| updated_at | DateTime | |

#### preference_memories (join table)

| Column | Type |
|--------|------|
| preference_id | UUID (FK, cascade delete) |
| memory_id | UUID (FK, cascade delete) |

#### style_profiles

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| profile_id | UUID (FK, UNIQUE) | One style profile per identity profile |
| tone | String | |
| humor_level | Float | 0.0–1.0 |
| verbosity | Float | 0.0–1.0 |
| formality | Float | 0.0–1.0 |
| vocabulary_notes | Text | Characteristic phrases, word choices |
| communication_patterns | Text | How they argue, explain, joke |
| source | String | "inferred" or "user" |
| created_at | DateTime | |
| updated_at | DateTime | |

### Connector System

#### connector_configs

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| connector_type | String | "gmail", "reddit" |
| credentials | Text | Encrypted JSON (OAuth tokens, API keys) |
| status | String | "active", "expired", "revoked" |
| created_at | DateTime | |
| updated_at | DateTime | |

### Access Tokens

#### access_tokens

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| name | String | Human-readable label, e.g. "Claude Desktop" |
| token_hash | String | SHA-256 hash of the bearer token |
| access_level | String | "owner" or "shared" |
| created_at | DateTime | |
| expires_at | DateTime (nullable) | Null = never expires |
| revoked_at | DateTime (nullable) | Null = active |

### Ingestion Jobs

#### ingestion_jobs

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| connector_type | String | "file", "gmail", "reddit" |
| status | String | "pending", "running", "completed", "failed" |
| started_at | DateTime (nullable) | |
| completed_at | DateTime (nullable) | |
| items_processed | Integer | Default 0 |
| items_failed | Integer | Default 0 |
| error_message | Text (nullable) | Last error if failed |
| created_at | DateTime | |

### Identity Snapshots

#### identity_snapshots

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| profile_id | UUID (FK) | |
| snapshot_data | JSONB | Full serialized identity (beliefs, preferences, style) |
| label | String (nullable) | Optional user-provided label |
| created_at | DateTime | |

### Photos

#### photos

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| profile_id | UUID (FK, nullable) | Nullable — photos can be ingested before profile exists |
| file_path | String | Local storage path |
| source | String | "upload", "gmail", "reddit" |
| source_ref | String | |
| description | Text | LLM-generated description |
| tags | String[] | "selfie", "group", "outdoor", etc. (GIN indexed for filtering) |
| is_reference | Boolean | Good reference image of the user |
| created_at | DateTime | |
| updated_at | DateTime | |

#### photo_people (join table)

| Column | Type |
|--------|------|
| photo_id | UUID (FK, cascade delete) |
| person_id | UUID (FK, cascade delete) |

---

## Ingestion Service

### Connector Interface

```python
class Connector(Protocol):
    async def configure(self, credentials: dict) -> None: ...
    async def fetch(self, options: dict) -> list[RawDocument]: ...

@dataclass
class RawDocument:
    content: str
    source: str             # "file", "gmail", "reddit"
    source_ref: str         # Filename, message ID, permalink
    timestamp: datetime
    authorship: str         # "user_authored", "received", "other_reply"
    images: list[bytes]     # Attached/embedded images
```

### File Upload Connector
- Accepts txt, md, json, jpg, png, webp via REST endpoint
- Text files: content extracted directly, authorship = "user_authored"
- Images: stored as photos, analyzed by LLM

### Gmail Connector
- Google OAuth client JSON path provided via config
- First-run OAuth flow: starts a temporary local HTTP server on `http://localhost:8090/callback` as the redirect URI. Opens the browser for Google consent. On callback, exchanges the auth code for tokens and stores the refresh token (encrypted) in connector_configs. For headless environments, falls back to manual copy-paste auth code flow.
- Fetches messages (configurable: all, date range, labels)
- Extracts plain text body + image attachments
- Authorship: sent = "user_authored", received = "received"

### Reddit Connector
- Uses PRAW (Python Reddit API Wrapper)
- Fetches user's posts, comments, saved items + image posts
- Authorship: user posts/comments = "user_authored", replies = "other_reply"

### Credential Setup
- `POST /api/connectors/{type}/configure` — setup credentials
- Gmail: accepts OAuth client JSON, triggers OAuth flow, stores tokens
- Reddit: accepts client_id/secret/username, validates, stores
- `GET /api/connectors` — returns status of all configured connectors

---

## Processing Pipeline

### Pipeline Flow

```
ingest(connector, options)
  → fetch raw documents (with authorship metadata)
  → for each document:
      normalize → chunk → embed
      → LLM analysis (intent, meaning, authorship-aware)
      → memory evolution (reinforce/degrade/evolve existing memories)
      → filter (discard irrelevant non-user content)
      → store memories with full analysis
  → for each image:
      store photo → LLM vision analysis → tag and link
```

### Stage 1: Normalize
- Strip HTML, decode entities, normalize whitespace
- Extract metadata (dates, email headers, etc.)
- Output: `ProcessedDocument(text, metadata)`

### Stage 2: Chunk
- Sentence-aware chunking, configurable size (~500 tokens default), overlap (~50 tokens)
- Short documents stay as one chunk
- Each chunk retains parent document reference

### Stage 3: Embed
- OpenAI text-embedding-ada-002 (1536 dimensions)
- Batch requests, rate limiting, retry

### Stage 4: LLM Analysis (Authorship-Aware)

**For user-authored content:**
- Intent: What was the user trying to say or do?
- Meaning: What does this reveal about the user's beliefs, values, preferences?
- Topics and people extraction
- Importance score based on identity relevance

**For others' content (only kept when relevant to user):**
- Is this a meaningful interaction?
- How did this shape or challenge the user's position?
- Relationship signal: What does this reveal about the relationship?

**Output:**
```python
@dataclass
class AnalyzedChunk:
    content: str
    embedding: list[float]
    authorship: str
    intent: str
    meaning: str
    topics: list[str]
    people: list[str]
    importance_score: float
    interaction_context: str | None
    keep: bool
```

### Stage 5: Memory Evolution
- Search for existing memories on the same topics
- Determine relationship: reinforces, contradicts, or adds nuance
- Trigger appropriate operation: reinforce, degrade, or evolve

---

## Memory System — Living Memory

### Core Principle

Memories are living records. They strengthen, weaken, split, and evolve as new data arrives — reflecting the variability of real humans.

### Memory Evolution Operations

**Reinforcement:**
- New data supports existing memory → importance_score increases, reinforcement_count increments
- Strongly reinforced memories carry more weight in identity inference

**Degradation:**
- New data contradicts existing memory → confidence decreases (not deleted)
- Memories aren't "wrong" — they represent what the person believed at that time
- last_reinforced_at tracks staleness

**Evolution/Splitting:**
- A belief becomes nuanced → LLM creates child memory linked via parent_memory_id
- Original marked as status="evolved"
- Captures: "I hate X" → "I hate X in context A but appreciate it in context B"

**Temporal Awareness:**
- All memories timestamped, recent data weighted more heavily via configurable decay (`MEMORY_DECAY_HALFLIFE_DAYS`, default 365 — memories lose half their recency weight per year)
- Queries can be time-scoped: "what did I think about X in 2023?"

### Memory Search Ranking

Results from `remember(query)` are ranked by a weighted composite score:

```
score = cosine_similarity * 0.5 + importance_score * 0.2 + recency_score * 0.2 + reinforcement_score * 0.1
```

Where:
- `cosine_similarity`: pgvector cosine distance to query embedding (0.0–1.0)
- `importance_score`: the memory's importance_score field (0.0–1.0)
- `recency_score`: exponential decay based on `MEMORY_DECAY_HALFLIFE_DAYS` (0.0–1.0)
- `reinforcement_score`: `min(reinforcement_count / 10, 1.0)`

### Memory Service Operations

| Operation | Description |
|-----------|-------------|
| `remember(query)` | Semantic search, returns memories with context |
| `recall_about(person\|topic)` | Everything the engram knows about a subject |
| `summarize_memories(filter)` | Claude narrative summary of filtered memories |
| `reinforce(memory_id, evidence)` | Boost importance, increment count |
| `degrade(memory_id, evidence)` | Lower confidence, link contradiction |
| `evolve(memory_id, nuance)` | Create child memory, mark parent evolved |
| `timeline(topic\|person)` | Show how a position changed over time |
| `find_contradictions()` | Surface active conflicts for review |
| `memory_stats()` | Counts, top topics, top people, source breakdown |

### Source Visibility

| Visibility | Behavior |
|------------|----------|
| `active` | Factored into memory/identity, visible to owner, used in engram responses |
| `private` | Used for owner queries only, excluded from third-party responses |
| `excluded` | Ignored by processing, inference, and RAG. Kept in DB. |

### Source Management API

- `GET /api/sources` — list sources with counts and visibility
- `PUT /api/sources/visibility` — change visibility (source_ref in request body to avoid URL encoding issues with paths/URLs)
- `DELETE /api/sources` — permanently delete source and its memories (source_ref in request body)
- `POST /api/sources/bulk` — bulk visibility changes

Visibility changes trigger re-tagging of affected memories. Identity inference can be re-triggered to recalculate.

---

## Identity Layer

### Identity Inference Engine

Runs periodically or on-demand after ingestion:

1. Query memories grouped by topic clusters
2. For each cluster, Claude analyzes: "Based on these memories (with timestamps, confidence, reinforcement), what does this person believe about [topic]?"
3. Compare against existing beliefs — reinforce, degrade, or create new
4. Same process for preferences and style
5. User-set records (source="user") are never overwritten — treated as ground truth

### User Override Flow

- `GET /api/identity/beliefs` — all inferred + user-set beliefs
- `PUT /api/identity/beliefs/{id}` — edit (sets source="user", never overwritten)
- `POST /api/identity/beliefs` — manually add
- `DELETE /api/identity/beliefs/{id}` — remove
- Same CRUD for preferences and style

### Identity Snapshots

- `POST /api/identity/snapshot` — save current state
- `GET /api/identity/snapshots` — list historical snapshots
- `GET /api/identity/snapshot/{id}` — view past identity
- Enables "who was I a year ago?" queries

---

## LLM Self Engine (RAG)

### RAG Pipeline

```
query("What do you think about remote work?")
  → 1. Embed query (OpenAI)
  → 2. Vector search memories (filtered by visibility + access level)
  → 3. Fetch identity context (beliefs, preferences, style)
  → 4. Assemble prompt
  → 5. Generate response (Claude)
```

### Prompt Assembly

```
You are {name}'s engram — a digital representation built from their real memories and identity.

IDENTITY:
{beliefs relevant to query}
{preferences relevant to query}

COMMUNICATION STYLE:
Tone: {tone}, Humor: {humor_level}, Verbosity: {verbosity}, Formality: {formality}
Patterns: {communication_patterns}
Vocabulary: {vocabulary_notes}

RELEVANT MEMORIES (most recent/reinforced first):
- [{date}] {content} (intent: {intent}, confidence: {confidence})
- ...

INSTRUCTIONS:
- Respond as this person would, based on the evidence above
- Favor more recent and higher-confidence memories when they conflict
- If insufficient information, say so in character
- Never fabricate beliefs or memories not supported by data
```

### Response Structure

```python
@dataclass
class EngramResponse:
    answer: str
    confidence: float
    memory_refs: list[UUID] | None       # Owner access only
    belief_refs: list[UUID] | None       # Owner access only
    sources: list[SourceCitation] | None # Owner access only
    caveats: list[str]

@dataclass
class SourceCitation:
    source: str
    source_ref: str
    timestamp: datetime
    snippet: str
```

### LLM Operations

| Operation | Description |
|-----------|-------------|
| `answer_as_self(query)` | Respond as the person |
| `summarize_self()` | "Who am I?" narrative summary |
| `simulate_decision(scenario)` | "How would I approach this?" |
| `compare_perspectives(topic, stance)` | "How does my view differ?" |
| `explain_belief(belief_id)` | Trace belief back to supporting memories |
| `list_topics()` | Topics the engram knows about, ranked |
| `list_opinions(topic)` | Positions on a topic with nuance and timeline |

---

## REST API

### Endpoints

**Ingestion:**
- `POST /api/ingest/file` — upload file(s)
- `POST /api/ingest/gmail` — trigger Gmail ingestion
- `POST /api/ingest/reddit` — trigger Reddit ingestion
- `GET /api/ingest/status` — ingestion job status

**Connectors:**
- `POST /api/connectors/{type}/configure` — set up credentials
- `GET /api/connectors` — list connector statuses
- `DELETE /api/connectors/{type}` — remove connector

**Memory:**
- `GET /api/memories?q=&topic=&person=&source=&from=&to=` — search/filter
- `GET /api/memories/{id}` — single memory detail
- `PUT /api/memories/{id}` — edit memory
- `DELETE /api/memories/{id}` — delete memory
- `GET /api/memories/timeline?topic=&person=` — chronological evolution
- `GET /api/memories/contradictions` — surface conflicting memories
- `GET /api/memories/stats` — memory counts, top topics, top people, source breakdown
- `POST /api/memories/summarize` — Claude narrative summary of filtered memories

**Sources:**
- `GET /api/sources` — list sources with counts and visibility
- `PUT /api/sources/visibility` — change visibility (source_ref in request body, avoids URL encoding issues)
- `DELETE /api/sources` — delete source and memories (source_ref in request body)
- `POST /api/sources/bulk` — bulk visibility changes

**Identity:**
- `GET /api/identity/profile` — full identity profile
- `PUT /api/identity/profile` — update profile name/description
- `GET /api/identity/beliefs` — all beliefs
- `PUT /api/identity/beliefs/{id}` — edit belief
- `POST /api/identity/beliefs` — add belief
- `DELETE /api/identity/beliefs/{id}` — remove belief
- Same CRUD for `/preferences`
- `PUT /api/identity/style` — upsert style profile (one per identity, UNIQUE constraint)
- `GET /api/identity/style` — get style profile
- `POST /api/identity/infer` — trigger re-inference
- `POST /api/identity/snapshot` — save snapshot
- `GET /api/identity/snapshots` — list snapshots
- `GET /api/identity/snapshot/{id}` — view a specific historical snapshot

**Engram:**
- `POST /api/engram/ask` — query the engram (owner mode with citations)
- `GET /api/engram/topics` — list known topics with opinion counts
- `GET /api/engram/opinions?topic=` — positions on a topic with nuance and timeline
- `GET /api/engram/summarize` — identity summary
- `POST /api/engram/simulate` — simulate decision (scenario in request body)
- `POST /api/engram/compare` — compare engram's perspective to another stance
- `GET /api/engram/explain-belief/{id}` — trace belief back to supporting memories
- `POST /api/engram/imagine` — generate image of engram in scenario
- `POST /api/engram/export` — export engram (no credentials)
- `POST /api/engram/import` — import engram

**Photos:**
- `POST /api/photos/upload` — upload reference photos
- `GET /api/photos` — list photos
- `PUT /api/photos/{id}` — edit metadata, toggle is_reference
- `DELETE /api/photos/{id}` — remove photo

**Config:**
- `GET /api/config` — current settings (redacted keys)
- `PUT /api/config/keys` — update API keys

**Tokens:**
- `POST /api/tokens` — create access token (owner or shared)
- `GET /api/tokens` — list tokens
- `DELETE /api/tokens/{id}` — revoke token

### Authentication

All REST API and MCP requests are authenticated via bearer token in the `Authorization` header:

```
Authorization: Bearer <token>
```

**Token lifecycle:**
- Tokens are generated via `POST /api/tokens` (requires an existing owner token, or the first token is created during `engram init`)
- Raw token is returned once at creation, then only the SHA-256 hash is stored
- Each token has an `access_level`: "owner" (full access + citations) or "shared" (limited endpoints, no source citations)
- Tokens can optionally expire (`expires_at`) or be revoked (`revoked_at`)

**Per-request flow:**
1. Extract bearer token from Authorization header
2. Hash it with SHA-256, look up in `access_tokens` table
3. Reject if not found, expired, or revoked
4. Set `access_level` on the request context (available via FastAPI dependency injection)

**Owner-only REST endpoints:** `/api/memories/*`, `/api/sources/*`, `/api/connectors/*`, `/api/identity/*` (write operations), `/api/config/*`, `/api/tokens/*`, `/api/ingest/*`, `/api/engram/export`, `/api/engram/import`

**Shared-accessible REST endpoints:** `/api/engram/ask`, `/api/engram/topics`, `/api/engram/opinions`, `/api/engram/summarize`, `/api/engram/simulate`, `/api/engram/compare`, `/api/engram/imagine`, `GET /api/identity/beliefs`, `GET /api/identity/profile`

### Async Ingestion

Ingestion is asynchronous. When an ingest endpoint is called:

1. Create an `ingestion_jobs` record with status="pending"
2. Return the job ID immediately (HTTP 202)
3. Processing runs as a background task via Redis queue (RQ worker)
4. Client polls `GET /api/ingest/status?job_id=` for progress
5. Job status progresses: pending → running → completed/failed

Redis is used as the job queue broker. The RQ worker runs as a separate process alongside the FastAPI server.

### Credential Encryption

Connector credentials (OAuth tokens, API keys) are encrypted at rest using Fernet symmetric encryption (from the `cryptography` library):

- A `ENGRAM_ENCRYPTION_KEY` is generated during `engram init` and stored in `.env`
- Generated via `cryptography.fernet.Fernet.generate_key()`
- Used to encrypt/decrypt the `credentials` JSON column in `connector_configs`
- If the key is lost, connector credentials must be re-configured

---

## MCP Server

Wraps the same service layer, exposed as MCP tools via the MCP Python SDK.

**Startup:** `engram server` starts the FastAPI REST API. `engram mcp` starts the MCP server as a separate process (stdio transport for Claude Desktop/Claude Code, or SSE transport for web clients). Both share the same database and service layer code but run as independent processes. The MCP server imports the same service modules and connects to the same Postgres instance.

### MCP Tools

| Tool | Description | Owner | Third-Party |
|------|-------------|-------|-------------|
| `answer_as_self` | Ask the engram a question | Yes (with citations) | Yes (no citations) |
| `search_memories` | Semantic memory search | Yes | No |
| `get_beliefs` | List beliefs by topic | Yes | Yes (no sources) |
| `get_opinions` | Opinions with nuance | Yes | Yes (no sources) |
| `list_topics` | Topics the engram knows about | Yes | Yes |
| `summarize_self` | Narrative identity summary | Yes | Yes |
| `simulate_decision` | Decision simulation | Yes | Yes |
| `recall_about` | Everything about a person/topic | Yes | No |
| `compare_perspectives` | Compare engram's view to another stance | Yes | Yes |
| `explain_belief` | Trace belief to supporting memories | Yes | No |
| `imagine` | Generate image of engram | Yes | Yes |

### Access Control
- Owner token: full access with citations
- Shared token: limited tools, no source citations
- Tokens managed via REST API

---

## Distribution & Setup Wizard

### Distribution
- PyPI package: `pip install engram` / `uv add engram`
- Docker Compose option for zero-Python setup
- GitHub repo for contributors

### CLI

```bash
engram init        # Run setup wizard
engram server      # Start FastAPI REST API + RQ worker
engram mcp         # Start MCP server (stdio or --sse for SSE transport)
engram ingest      # Run ingestion manually
engram status      # Show engram stats
```

### Setup Wizard (`engram init`)

**Step 1: Infrastructure**
- Check for Docker → spin up Postgres+pgvector and Redis
- OR accept existing Postgres connection string
- Verify pgvector, run Alembic migrations

**Step 2: API Keys + First Token**
- Prompt for Anthropic API key (required)
- Prompt for OpenAI API key (required)
- Validate both, store in .env
- Generate and display the first owner access token (save this — it's shown only once)

**Step 3: Identity Profile**
- Ask for name, optional description
- Upload reference photos (optional)
- Create default identity_profile

**Step 4: Data Connectors (optional)**
- File upload: provide directory path
- Gmail: walk through OAuth setup, browser auth, cache tokens
- Reddit: enter client_id/secret, validate
- Each independently optional

**Step 5: Initial Ingestion**
- Run first ingestion if connectors configured
- Show progress and report

**Step 6: Verify**
- Test query against engram
- Show response + stats
- "Your engram is ready."

### Import/Export

```bash
engram import engram-export.json    # Load existing engram
```

- Export: all memories, identity, photos metadata (no credentials)
- After import, MCP server works immediately

---

## Photos & Visual Identity

### Photo Ingestion
- Direct upload via API or setup wizard
- Connector extraction: Gmail attachments, Reddit image posts, file uploads
- LLM vision analysis: description, tags, people identification
- User marks best reference photos (is_reference=True)

### Image Generation
```
imagine(scenario)
  → Fetch reference photos (is_reference=True)
  → Fetch style profile + identity context
  → Build prompt with appearance + scenario
  → Send to OpenAI GPT Image (gpt-image-1)
  → Return generated image
```

### Privacy
- Reference photos never exposed to third-party access
- Generated images can be shared (synthetic)
- Photo visibility follows active/private/excluded model

### Storage
- Photos stored locally in configurable directory (default ~/.engram/photos/)
- Database stores metadata and path only

---

## Configuration

All configuration is via Pydantic `BaseSettings` reading from environment variables / `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/engram` | Postgres connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `ANTHROPIC_API_KEY` | (required) | Claude API key |
| `OPENAI_API_KEY` | (required) | OpenAI API key (embeddings + image generation) |
| `ENGRAM_ENCRYPTION_KEY` | (generated by `engram init`) | Fernet key for credential encryption |
| `CHUNK_SIZE_TOKENS` | `500` | Max tokens per chunk |
| `CHUNK_OVERLAP_TOKENS` | `50` | Overlap between chunks |
| `MEMORY_DECAY_HALFLIFE_DAYS` | `365` | How fast recency weight decays |
| `EMBEDDING_MODEL` | `text-embedding-ada-002` | OpenAI embedding model |
| `EMBEDDING_DIMENSIONS` | `1536` | Embedding vector size |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Claude model for analysis/generation |
| `PHOTO_STORAGE_DIR` | `~/.engram/photos` | Local directory for photo storage |
| `SERVER_HOST` | `0.0.0.0` | FastAPI bind host |
| `SERVER_PORT` | `8000` | FastAPI bind port |
| `MCP_TRANSPORT` | `stdio` | MCP transport: "stdio" or "sse" |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Redis Usage

Redis serves two purposes:

1. **Job queue** (via RQ): Ingestion jobs are enqueued to Redis and processed by a separate RQ worker process. This keeps the FastAPI server responsive during long-running ingestion.

2. **Embedding cache**: Embedding results are cached in Redis with the content hash as key. If the same text is re-processed (e.g., re-ingestion), the cached embedding is used instead of calling OpenAI again. TTL: 30 days.

---

## LLM Error Handling

All LLM API calls (Claude and OpenAI) use a shared retry strategy:

- **Retry**: exponential backoff, max 3 retries (1s, 2s, 4s)
- **Rate limits (HTTP 429)**: respect `Retry-After` header, wait and retry
- **Timeout**: 60s per request for generation, 30s for embeddings
- **Batch failures**: if an embedding batch fails, retry individual items; log and skip items that fail 3 times
- **Processing failures**: if LLM analysis fails for a chunk, store the memory with `intent=null` and `meaning=null` and flag for re-processing. Don't block the entire ingestion job.

---

## Export/Import Format

The export file is a self-contained JSON document:

```json
{
  "version": "1.0",
  "exported_at": "2026-03-22T12:00:00Z",
  "profile": {
    "name": "...",
    "description": "..."
  },
  "memories": [
    {
      "content": "...",
      "intent": "...",
      "meaning": "...",
      "timestamp": "...",
      "source": "...",
      "source_ref": "...",
      "authorship": "...",
      "importance_score": 0.8,
      "confidence": 0.9,
      "reinforcement_count": 3,
      "status": "active",
      "visibility": "active",
      "topics": ["topic1", "topic2"],
      "people": [{"name": "...", "relationship": "..."}]
    }
  ],
  "beliefs": [...],
  "preferences": [...],
  "style_profile": {...},
  "photos": [
    {
      "description": "...",
      "tags": [...],
      "is_reference": true,
      "base64_data": "..."
    }
  ]
}
```

**Excluded from export:** API keys, connector credentials, access tokens, embeddings (re-generated on import), ingestion job history.

**Import process:**
1. Create identity profile from export data
2. Re-embed all memory content (using the importer's OpenAI key)
3. Recreate topic/people records and links
4. Store beliefs, preferences, style profile
5. Store photos to local filesystem

---

## Evaluation & Testing

### Unit Tests (per module)

**Ingestion:** connector parsing, authorship tagging, credential storage
**Processing:** normalization, chunking, embedding dimensions, LLM analysis extraction, authorship filtering
**Memory:** CRUD, vector search, filtered search, reinforcement, degradation, evolution, visibility filtering
**Identity:** inference from memories, user override protection, snapshot capture/restore
**LLM/RAG:** prompt assembly, owner vs third-party response shapes, topic listing
**API:** status codes, auth validation, access level enforcement
**MCP:** tool responses, access control per tool
**Photos:** upload/store, reference retrieval, privacy enforcement

### Integration Tests

- Full pipeline: upload file → process → memories appear → search works
- Identity flow: ingest → infer → beliefs populated → query engram → response uses beliefs
- Evolution flow: ingest contradiction → memory degrades → belief updates
- Privacy flow: set source private → third-party query excludes it

### Acceptance Criteria Format

Each implementation step includes programmatic checks:
```
ACCEPTANCE:
- [ ] `pytest tests/test_<module>/ -v` passes
- [ ] Server starts without errors
- [ ] Specific curl/API verification commands pass
- [ ] Performance targets met
```

---

## Build Order

Bottom-up, each step builds on the last. REST routes are built alongside their service layer, not as a separate step.

1. **Project scaffold** — pyproject.toml, Docker Compose (pgvector + Redis), Alembic setup, config module (all env vars), DB engine, .gitignore, .env.example, README.md
2. **Data models + migrations** — all SQLAlchemy models, Alembic migration to create all tables (including indexes: GIN on tags, HNSW/IVFFlat on embedding vectors)
3. **Auth system + tokens API** — token model, token CRUD (`POST/GET/DELETE /api/tokens`), first owner token creation, bearer auth FastAPI dependency, access level middleware. This must be complete before any other API route, since all routes depend on auth.
4. **Config API** — `GET /api/config`, `PUT /api/config/keys`
5. **File ingestion connector** — connector protocol, file connector, `POST /api/ingest/file`, async job queue with RQ worker, `GET /api/ingest/status`, connector CRUD (`POST /api/connectors/{type}/configure`, `GET /api/connectors`, `DELETE /api/connectors/{type}`)
6. **Processing pipeline (stages 1-3)** — normalizer, chunker, embedder (OpenAI). These are the non-LLM stages. Build and test independently: file in → normalized text → chunks → embeddings stored. Memory evolution (stage 5) is NOT connected yet.
7. **LLM analysis (stage 4)** — Claude-powered intent/meaning/authorship analysis, analyzer module. Extends the pipeline: chunks now get analyzed. Still stores memories without evolution.
8. **Memory system + API** — repository (CRUD, vector search, filtered search), service (remember, recall, reinforce, degrade, evolve, timeline, contradictions, stats, summarize), all `/api/memories/*` and `/api/sources/*` routes. **After this step, connect memory evolution (pipeline stage 5) so the full pipeline runs end-to-end:** new ingestions now check for existing memories and reinforce/degrade/evolve as needed.
9. **Identity layer + API** — inference engine, repository, service (overrides, snapshots), all `/api/identity/*` routes including snapshot CRUD
10. **RAG engine + engram API** — prompt assembly, response generation, `/api/engram/*` routes: ask, topics, opinions, summarize, simulate, compare, explain-belief. Note: `imagine` endpoint comes in step 14.
11. **MCP server** — MCP Python SDK integration, all tools (except `imagine`), access control, `engram mcp` CLI command. **Startup:** `engram server` starts FastAPI + spawns RQ worker as a subprocess. `engram mcp` is a separate command/process.
12. **Gmail connector** — OAuth flow (local redirect on `localhost:8090/callback` + headless manual code fallback), Gmail API fetch, `/api/connectors/gmail/configure`
13. **Reddit connector** — PRAW integration, fetch posts/comments/saved, `/api/connectors/reddit/configure`
14. **Photo system + image generation** — photo upload/storage, LLM vision analysis, GPT Image generation, `/api/photos/*` routes, `POST /api/engram/imagine`, `imagine` MCP tool
15. **Export/import** — export JSON format, `POST /api/engram/export`, `POST /api/engram/import`, `engram import` CLI
16. **Setup wizard** — `engram init` interactive CLI (infrastructure, keys, profile, connectors, initial ingestion, verify). Depends on steps 1-5 and 12-13 being complete.
17. **Distribution packaging** — PyPI setup, `engram` CLI entry points in pyproject.toml
18. **Integration tests** — full pipeline, identity flow, evolution flow, privacy flow

**Shared-access field redaction:** When a shared token accesses `GET /api/identity/beliefs` or `GET /api/identity/profile`, the response omits: `source` field, `belief_memories` associations, and `supporting_memory` links. For `POST /api/engram/ask`, shared responses omit `memory_refs`, `belief_refs`, and `sources`. The `style` endpoint uses `PUT` (upsert) since there's one style profile per identity (UNIQUE constraint on profile_id).

**Request body note for `POST /api/engram/compare`:** Expects `{ "topic": "...", "stance": "..." }` where `stance` is the external perspective to compare against.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Privacy (storing personal data) | All local, user-controlled, encrypted credentials, visibility controls |
| Hallucination (engram says things the person never said) | Strict grounding in memories, confidence scores, "insufficient data" responses |
| Identity drift (engram diverges from real person) | Memory evolution tracking, user overrides, snapshots, contradiction detection |
| API costs (Claude + OpenAI) | Batching, caching embeddings, configurable processing depth |
| Connector auth complexity | Setup wizard, token caching, clear error messages |

---

## Future Considerations

- Voice synthesis
- Video avatars
- Continuous learning (real-time ingestion)
- Multi-agent identities
- Additional connectors (Twitter/X, Discord, Slack, etc.)
- Web UI for memory/identity management
