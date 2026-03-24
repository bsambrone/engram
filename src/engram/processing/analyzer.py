import json
from dataclasses import dataclass

from engram.llm.providers import generate

ANALYSIS_SYSTEM_PROMPT = """\
You analyze text to extract identity signals. Return valid JSON only, no markdown fences.

For user-authored content, extract:
- intent: What the user was trying to say or do (string)
- meaning: What this reveals about their beliefs, values, preferences (string)
- topics: Key topics mentioned (list of strings)
- people: People mentioned by name (list of strings)
- importance_score: 0.0-1.0 based on identity relevance (float)
- keep: always true for user content (boolean)

For others' content (authorship is "received" or "other_reply"), extract:
- intent: What the other person was doing (string)
- meaning: How this shaped or challenged the user's position (string)
- topics, people, importance_score as above
- keep: false if no identity signal (e.g. "lol", "ok", small talk)

People extraction rules:
- Include @mentions (strip the @ prefix, keep the username): "@johndoe" -> "johndoe"
- Include names in natural language: "my wife Sarah" -> "Sarah", "Aubrey decorated" -> "Aubrey"
- Include full names when available: "John Smith tagged you" -> "John Smith"
- Do NOT include generic references like "my friend" without a name
- Return each person only once, even if mentioned multiple times"""


@dataclass
class AnalyzedChunk:
    content: str
    embedding: list[float]
    authorship: str
    intent: str | None
    meaning: str | None
    topics: list[str]
    people: list[str]
    importance_score: float
    interaction_context: str | None
    keep: bool


async def analyze_chunk(
    content: str, authorship: str, embedding: list[float]
) -> AnalyzedChunk:
    """Analyze a text chunk using the LLM to extract identity signals."""
    try:
        raw = await generate(
            system=ANALYSIS_SYSTEM_PROMPT,
            user=f"Authorship: {authorship}\n\nContent:\n{content}",
            max_tokens=1024,
        )
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        data = {
            "intent": None,
            "meaning": None,
            "topics": [],
            "people": [],
            "importance_score": 0.5,
            "keep": authorship == "user_authored",
        }

    return AnalyzedChunk(
        content=content,
        embedding=embedding,
        authorship=authorship,
        intent=data.get("intent"),
        meaning=data.get("meaning"),
        topics=data.get("topics", []),
        people=data.get("people", []),
        importance_score=data.get("importance_score", 0.5),
        interaction_context=data.get("interaction_context"),
        keep=data.get("keep", True),
    )
