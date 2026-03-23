"""MCP server exposing the engram as tools for Claude Desktop, Claude Code, etc."""

from __future__ import annotations

import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from engram.identity.service import IdentityService
from engram.llm.providers import generate
from engram.llm.rag import ask_engram
from engram.memory.service import MemoryService
from engram.processing.embedder import embed_texts

# Lazy import — avoid importing db at module level so tests can patch it.
# The actual async_session factory is imported inside tool handlers.
async_session = None  # set by _ensure_session_factory()

TOOL_NAMES = [
    "answer_as_self",
    "list_topics",
    "summarize_self",
    "simulate_decision",
    "get_beliefs",
    "get_opinions",
    "search_memories",
    "recall_about",
    "compare_perspectives",
]

server = Server("engram")


def _ensure_session_factory():
    """Lazily import the async_session factory from engram.db."""
    global async_session  # noqa: PLW0603
    if async_session is None:
        from engram.db import async_session as _factory

        async_session = _factory


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return all available engram tools."""
    return [
        Tool(
            name="answer_as_self",
            description="Ask the engram a question and get a response as this person would answer",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question to ask the engram",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_topics",
            description="List topics the engram knows about, with memory counts",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="summarize_self",
            description="Get a first-person narrative identity summary",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="simulate_decision",
            description="Simulate how this person would decide in a given scenario",
            inputSchema={
                "type": "object",
                "properties": {
                    "scenario": {
                        "type": "string",
                        "description": "The decision scenario to simulate",
                    },
                },
                "required": ["scenario"],
            },
        ),
        Tool(
            name="get_beliefs",
            description="List beliefs held by this person, optionally filtered by topic",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Optional topic to filter beliefs by",
                    },
                },
            },
        ),
        Tool(
            name="get_opinions",
            description="Get opinions on a specific topic with nuance and confidence",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic to get opinions about",
                    },
                },
                "required": ["topic"],
            },
        ),
        Tool(
            name="search_memories",
            description="Semantic search across all memories",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for semantic memory search",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="recall_about",
            description="Recall everything about a specific person or topic",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "The person or topic to recall memories about",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10)",
                    },
                },
                "required": ["subject"],
            },
        ),
        Tool(
            name="compare_perspectives",
            description="Compare this person's view on a topic with another stance",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic to compare perspectives on",
                    },
                    "other_stance": {
                        "type": "string",
                        "description": "The alternative stance to compare against",
                    },
                },
                "required": ["topic", "other_stance"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch a tool call to the appropriate handler."""
    _ensure_session_factory()

    try:
        if name == "answer_as_self":
            return await _handle_answer_as_self(arguments)
        elif name == "list_topics":
            return await _handle_list_topics(arguments)
        elif name == "summarize_self":
            return await _handle_summarize_self(arguments)
        elif name == "simulate_decision":
            return await _handle_simulate_decision(arguments)
        elif name == "get_beliefs":
            return await _handle_get_beliefs(arguments)
        elif name == "get_opinions":
            return await _handle_get_opinions(arguments)
        elif name == "search_memories":
            return await _handle_search_memories(arguments)
        elif name == "recall_about":
            return await _handle_recall_about(arguments)
        elif name == "compare_perspectives":
            return await _handle_compare_perspectives(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as exc:
        return [TextContent(type="text", text=f"Error in {name}: {exc}")]


# ---------------------------------------------------------------------------
# Individual tool handlers
# ---------------------------------------------------------------------------


async def _handle_answer_as_self(arguments: dict) -> list[TextContent]:
    """Ask the engram a question using the full RAG pipeline."""
    query = arguments.get("query", "")
    async with async_session() as session:
        response = await ask_engram(session, query, is_owner=False)
    text = response.answer
    if response.caveats:
        text += "\n\n(Note: " + "; ".join(response.caveats) + ")"
    return [TextContent(type="text", text=text)]


async def _handle_list_topics(arguments: dict) -> list[TextContent]:
    """Query the Topic table and return topics with memory counts."""
    from sqlalchemy import func, select

    from engram.models.memory import MemoryTopic, Topic

    async with async_session() as session:
        result = await session.execute(
            select(Topic.name, func.count(MemoryTopic.memory_id))
            .outerjoin(MemoryTopic, Topic.id == MemoryTopic.topic_id)
            .group_by(Topic.name)
            .order_by(func.count(MemoryTopic.memory_id).desc())
        )
        rows = result.all()

    if not rows:
        return [TextContent(type="text", text="No topics found yet.")]

    lines = ["Topics:"]
    for topic_name, count in rows:
        lines.append(f"  - {topic_name} ({count} memories)")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_summarize_self(arguments: dict) -> list[TextContent]:
    """Get the full identity and ask the LLM for a first-person summary."""
    async with async_session() as session:
        svc = IdentityService(session)
        profile = await svc.get_or_create_default_profile()
        identity = await svc.get_full_identity(profile.id)

    identity_json = json.dumps(identity, indent=2, default=str)
    summary = await generate(
        system=(
            f"You are {profile.name}. Based on the identity data below, "
            "write a first-person narrative summary of who you are. "
            "Be authentic and personal. Keep it to 2-3 paragraphs."
        ),
        user=f"Identity data:\n{identity_json}",
    )

    return [TextContent(type="text", text=summary)]


async def _handle_simulate_decision(arguments: dict) -> list[TextContent]:
    """Simulate how the person would decide in a given scenario."""
    scenario = arguments.get("scenario", "")
    query = (
        f"You are faced with the following decision scenario. "
        f"Based on your values, beliefs, and past patterns, "
        f"how would you approach this decision?\n\n"
        f"Scenario: {scenario}"
    )
    async with async_session() as session:
        response = await ask_engram(session, query, is_owner=False)
    text = response.answer
    if response.caveats:
        text += "\n\n(Note: " + "; ".join(response.caveats) + ")"
    return [TextContent(type="text", text=text)]


async def _handle_get_beliefs(arguments: dict) -> list[TextContent]:
    """List beliefs, optionally filtered by topic."""
    topic_filter = arguments.get("topic")

    async with async_session() as session:
        svc = IdentityService(session)
        profile = await svc.get_or_create_default_profile()
        identity = await svc.get_full_identity(profile.id)

    beliefs = identity["beliefs"]
    if topic_filter:
        beliefs = [b for b in beliefs if b.get("topic", "").lower() == topic_filter.lower()]

    if not beliefs:
        msg = "No beliefs found"
        if topic_filter:
            msg += f" for topic '{topic_filter}'"
        return [TextContent(type="text", text=msg + ".")]

    lines = ["Beliefs:"]
    for b in beliefs:
        line = f"  - {b.get('topic', 'unknown')}: {b.get('stance', 'no stance')}"
        if b.get("nuance"):
            line += f" ({b['nuance']})"
        if b.get("confidence") is not None:
            line += f" [confidence: {b['confidence']}]"
        lines.append(line)

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_get_opinions(arguments: dict) -> list[TextContent]:
    """Get opinions on a specific topic with nuance and confidence."""
    topic = arguments.get("topic", "")

    async with async_session() as session:
        svc = IdentityService(session)
        profile = await svc.get_or_create_default_profile()
        identity = await svc.get_full_identity(profile.id)

    # Filter beliefs by topic (case-insensitive partial match)
    beliefs = [
        b for b in identity["beliefs"]
        if topic.lower() in b.get("topic", "").lower()
    ]

    if not beliefs:
        return [TextContent(
            type="text",
            text=f"No opinions found on '{topic}'.",
        )]

    lines = [f"Opinions on '{topic}':"]
    for b in beliefs:
        line = f"  - {b.get('stance', 'no stance')}"
        if b.get("nuance"):
            line += f"\n    Nuance: {b['nuance']}"
        if b.get("confidence") is not None:
            line += f"\n    Confidence: {b['confidence']}"
        lines.append(line)

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_search_memories(arguments: dict) -> list[TextContent]:
    """Embed the query and search via MemoryService."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)

    query_embeddings = await embed_texts([query])

    async with async_session() as session:
        svc = MemoryService(session)
        memories = await svc.remember(
            query_embeddings[0], limit=limit, visibility="active"
        )

    if not memories:
        return [TextContent(type="text", text="No matching memories found.")]

    lines = [f"Found {len(memories)} memories:"]
    for m in memories:
        ts = m.timestamp.isoformat() if m.timestamp else "unknown"
        lines.append(f"  - [{ts}] {m.content[:200]}")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_recall_about(arguments: dict) -> list[TextContent]:
    """Recall everything about a person or topic by embedding the subject."""
    subject = arguments.get("subject", "")
    limit = arguments.get("limit", 10)

    query_embeddings = await embed_texts([subject])

    async with async_session() as session:
        svc = MemoryService(session)
        memories = await svc.remember(
            query_embeddings[0], limit=limit, visibility="active"
        )

    if not memories:
        return [TextContent(type="text", text=f"No memories found about '{subject}'.")]

    lines = [f"Memories about '{subject}':"]
    for m in memories:
        ts = m.timestamp.isoformat() if m.timestamp else "unknown"
        lines.append(f"  - [{ts}] {m.content[:200]}")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_compare_perspectives(arguments: dict) -> list[TextContent]:
    """Compare the person's view on a topic with another stance."""
    topic = arguments.get("topic", "")
    other_stance = arguments.get("other_stance", "")

    query = (
        f"Compare your personal perspective on '{topic}' with "
        f"the following alternative stance: '{other_stance}'. "
        f"Where do you agree? Where do you differ? Why?"
    )

    async with async_session() as session:
        response = await ask_engram(session, query, is_owner=False)

    text = response.answer
    if response.caveats:
        text += "\n\n(Note: " + "; ".join(response.caveats) + ")"
    return [TextContent(type="text", text=text)]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main():
    """Run the MCP server over stdio transport."""
    _ensure_session_factory()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
