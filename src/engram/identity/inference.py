"""Identity inference engine — LLM-powered trait extraction from memories."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engram.identity.repository import IdentityRepository
from engram.llm.providers import generate
from engram.models.memory import Memory

INFERENCE_SYSTEM_PROMPT = """\
You are an identity analyst. Given a set of personal memories, extract the user's beliefs, \
preferences, and communication style.

Return valid JSON with this structure:
{
  "beliefs": [{"topic": "...", "stance": "...", "nuance": "...", "confidence": 0.0-1.0}],
  "preferences": [{"category": "...", "value": "...", "strength": 0.0-1.0}],
  "style": {
    "tone": "...",
    "humor_level": 0.0-1.0,
    "verbosity": 0.0-1.0,
    "formality": 0.0-1.0,
    "vocabulary_notes": "...",
    "communication_patterns": "..."
  }
}

Only include traits you can confidently infer from the memories provided.
"""


async def run_inference(session: AsyncSession, profile_id: uuid.UUID) -> dict:
    """Analyze recent high-importance user-authored memories and extract identity traits."""
    repo = IdentityRepository(session)

    # Get recent high-importance user-authored memories
    stmt = (
        select(Memory)
        .where(Memory.authorship == "user")
        .where(Memory.status == "active")
        .where(Memory.importance_score.isnot(None))
        .order_by(Memory.importance_score.desc())
        .limit(50)
    )
    result = await session.execute(stmt)
    memories = result.scalars().all()

    if not memories:
        return {"status": "no_memories", "extracted": 0}

    # Format memories for the LLM
    memory_texts = [f"- {m.content}" for m in memories]
    user_prompt = "Here are the user's memories:\n\n" + "\n".join(memory_texts)

    # Call LLM
    raw_response = await generate(INFERENCE_SYSTEM_PROMPT, user_prompt, max_tokens=4096)

    # Parse LLM response
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        return {"status": "parse_error", "extracted": 0}

    extracted = 0

    # Create/update inferred beliefs (never overwrite source="user")
    for belief_data in data.get("beliefs", []):
        topic = belief_data.get("topic", "")
        if not topic:
            continue
        # Check if there's already a user-sourced belief on this topic
        existing = await repo.list_beliefs(profile_id, topic=topic)
        user_beliefs = [b for b in existing if b.source == "user"]
        if user_beliefs:
            continue  # Don't overwrite user-sourced beliefs
        # Check for existing inferred belief on this topic to update
        inferred = [b for b in existing if b.source == "inferred"]
        if inferred:
            await repo.update_belief(
                inferred[0].id,
                stance=belief_data.get("stance"),
                nuance=belief_data.get("nuance"),
                confidence=belief_data.get("confidence"),
            )
        else:
            await repo.create_belief(
                profile_id,
                topic=topic,
                stance=belief_data.get("stance"),
                nuance=belief_data.get("nuance"),
                confidence=belief_data.get("confidence"),
                source="inferred",
            )
        extracted += 1

    # Create/update inferred preferences
    for pref_data in data.get("preferences", []):
        category = pref_data.get("category", "")
        if not category:
            continue
        existing = await repo.list_preferences(profile_id)
        user_prefs = [p for p in existing if p.source == "user" and p.category == category]
        if user_prefs:
            continue
        inferred_prefs = [p for p in existing if p.source == "inferred" and p.category == category]
        if inferred_prefs:
            await repo.update_preference(
                inferred_prefs[0].id,
                value=pref_data.get("value"),
                strength=pref_data.get("strength"),
            )
        else:
            await repo.create_preference(
                profile_id,
                category=category,
                value=pref_data.get("value"),
                strength=pref_data.get("strength"),
                source="inferred",
            )
        extracted += 1

    # Update style if present (only if no user-sourced style exists)
    style_data = data.get("style")
    if style_data:
        existing_style = await repo.get_style(profile_id)
        if existing_style is None or existing_style.source != "user":
            await repo.upsert_style(
                profile_id,
                tone=style_data.get("tone"),
                humor_level=style_data.get("humor_level"),
                verbosity=style_data.get("verbosity"),
                formality=style_data.get("formality"),
                vocabulary_notes=style_data.get("vocabulary_notes"),
                communication_patterns=style_data.get("communication_patterns"),
                source="inferred",
            )
            extracted += 1

    return {"status": "ok", "extracted": extracted}
