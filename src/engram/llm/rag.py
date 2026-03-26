"""RAG pipeline — embed query, search memories, fetch identity, assemble prompt, generate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from engram.identity.service import IdentityService
from engram.llm.providers import generate
from engram.memory.service import MemoryService
from engram.processing.embedder import embed_texts


@dataclass
class EngramResponse:
    """Structured response from the engram RAG pipeline."""

    answer: str
    confidence: float
    memory_refs: list[str] | None = None
    belief_refs: list[str] | None = None
    caveats: list[str] = field(default_factory=list)


def build_prompt(
    name: str,
    beliefs: list[dict],
    preferences: list[dict],
    style: dict | None,
    memories: list[dict],
    as_of_date: datetime | None = None,
) -> str:
    """Build the system prompt that makes the LLM respond as the person.

    Combines identity information (beliefs, preferences, style) and relevant
    memories into a structured system prompt.
    """
    sections = []

    base_instruction = (
        f"You are the digital engram of {name}. "
        "Respond as this person would, based on their memories, beliefs, "
        "preferences, and communication style. "
        "Stay faithful to the data provided. If the data is insufficient, "
        "say so rather than fabricating."
    )
    if as_of_date:
        base_instruction += (
            f"\n\nIMPORTANT: Respond as this person would have on "
            f"{as_of_date.strftime('%Y-%m-%d')}. Only use beliefs, preferences, "
            f"and memories from that date or earlier."
        )
    sections.append(base_instruction)

    # Beliefs
    if beliefs:
        lines = ["## Beliefs"]
        for b in beliefs:
            line = f"- {b.get('topic', 'unknown')}: {b.get('stance', 'no stance')}"
            if b.get("confidence"):
                line += f" (confidence: {b['confidence']})"
            lines.append(line)
        sections.append("\n".join(lines))

    # Preferences
    if preferences:
        lines = ["## Preferences"]
        for p in preferences:
            line = f"- {p.get('category', 'general')}: {p.get('value', 'unknown')}"
            if p.get("strength"):
                line += f" (strength: {p['strength']})"
            lines.append(line)
        sections.append("\n".join(lines))

    # Style
    if style:
        lines = ["## Communication Style"]
        if style.get("tone"):
            lines.append(f"- Tone: {style['tone']}")
        if style.get("humor_level") is not None:
            lines.append(f"- Humor level: {style['humor_level']}")
        if style.get("verbosity") is not None:
            lines.append(f"- Verbosity: {style['verbosity']}")
        if style.get("formality") is not None:
            lines.append(f"- Formality: {style['formality']}")
        if style.get("vocabulary_notes"):
            lines.append(f"- Vocabulary: {style['vocabulary_notes']}")
        if style.get("communication_patterns"):
            lines.append(f"- Patterns: {style['communication_patterns']}")
        sections.append("\n".join(lines))

    # Memories — separated by authorship so the LLM knows what YOU said vs what others said
    user_memories = [m for m in memories if m.get("authorship") == "user_authored"]
    received_memories = [m for m in memories if m.get("authorship") != "user_authored"]

    if user_memories:
        lines = ["## Your Memories (things you said/wrote — primary identity signal)"]
        for m in user_memories:
            content = m.get("content", "")
            intent = m.get("intent", "")
            confidence = m.get("confidence", "")
            timestamp = m.get("timestamp", "")
            entry = f"- [{timestamp}] ({intent}, conf={confidence}) {content}"
            lines.append(entry)
        sections.append("\n".join(lines))

    if received_memories:
        lines = [
            "## Context from others (things others said to you — weak signal, "
            "use only as context for what you were exposed to, NOT as your own views)"
        ]
        for m in received_memories:
            content = m.get("content", "")
            timestamp = m.get("timestamp", "")
            meaning = m.get("meaning", "")
            entry = f"- [{timestamp}] {content}"
            if meaning:
                entry += f" (context: {meaning})"
            lines.append(entry)
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


async def ask_engram(
    session: AsyncSession,
    query: str,
    *,
    is_owner: bool = True,
    as_of_date: datetime | None = None,
) -> EngramResponse:
    """Full RAG pipeline: embed -> search -> identity -> prompt -> generate."""
    identity_svc = IdentityService(session)
    memory_svc = MemoryService(session)

    profile = await identity_svc.get_or_create_default_profile()
    identity = await identity_svc.get_full_identity(profile.id, as_of_date=as_of_date)

    # Embed query and search memories
    query_embeddings = await embed_texts([query])
    # Owner sees active + private; shared sees only active
    visibility = None if is_owner else "active"
    memories = await memory_svc.remember(
        query_embeddings[0],
        limit=15,
        visibility=visibility,
        before_date=as_of_date,
    )

    memory_dicts = [
        {
            "content": m.content,
            "intent": m.intent,
            "meaning": m.meaning,
            "confidence": m.confidence,
            "authorship": m.authorship,
            "timestamp": m.timestamp.isoformat() if m.timestamp else None,
        }
        for m in memories
    ]

    system_prompt = build_prompt(
        name=profile.name,
        beliefs=identity["beliefs"],
        preferences=identity["preferences"],
        style=identity["style"],
        memories=memory_dicts,
        as_of_date=as_of_date,
    )

    answer = await generate(system=system_prompt, user=query)

    return EngramResponse(
        answer=answer,
        confidence=sum(m.confidence for m in memories) / max(len(memories), 1),
        memory_refs=[str(m.id) for m in memories] if is_owner else None,
        belief_refs=[b["id"] for b in identity["beliefs"]] if is_owner else None,
        caveats=["Limited data available"] if len(memories) < 3 else [],
    )
