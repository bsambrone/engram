"""Tests for engram conversation API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from engram.llm.rag import EngramResponse


def _mock_ask_engram_result(**overrides):
    """Build a default EngramResponse for testing."""
    defaults = {
        "answer": "This is the engram answer.",
        "confidence": 0.75,
        "memory_refs": ["mem-1", "mem-2"],
        "belief_refs": ["belief-1"],
        "caveats": [],
    }
    defaults.update(overrides)
    return EngramResponse(**defaults)


# ---------------------------------------------------------------------------
# POST /api/engram/ask
# ---------------------------------------------------------------------------


async def test_ask_returns_answer(test_client: AsyncClient):
    """POST /api/engram/ask returns an answer from the engram."""
    with patch(
        "engram.api.routes.engram.ask_engram",
        new_callable=AsyncMock,
        return_value=_mock_ask_engram_result(),
    ):
        resp = await test_client.post(
            "/api/engram/ask",
            json={"query": "What do I think about Python?"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "This is the engram answer."
    assert body["confidence"] == 0.75
    assert body["memory_refs"] is not None
    assert body["belief_refs"] is not None


async def test_ask_requires_query(test_client: AsyncClient):
    """POST /api/engram/ask returns 422 without query field."""
    resp = await test_client.post("/api/engram/ask", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/engram/topics
# ---------------------------------------------------------------------------


async def test_topics_returns_list(test_client: AsyncClient):
    """GET /api/engram/topics returns a list of topics with counts."""
    resp = await test_client.get("/api/engram/topics")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


# ---------------------------------------------------------------------------
# GET /api/engram/opinions
# ---------------------------------------------------------------------------


async def test_opinions_requires_topic(test_client: AsyncClient):
    """GET /api/engram/opinions without topic returns 422."""
    resp = await test_client.get("/api/engram/opinions")
    assert resp.status_code == 422


async def test_opinions_returns_beliefs(test_client: AsyncClient):
    """GET /api/engram/opinions?topic=X returns beliefs for that topic."""
    # First create a belief so there's data
    await test_client.post(
        "/api/identity/beliefs",
        json={"topic": "opinions-test-topic", "stance": "positive", "confidence": 0.9},
    )
    resp = await test_client.get("/api/engram/opinions?topic=opinions-test-topic")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


# ---------------------------------------------------------------------------
# GET /api/engram/summarize
# ---------------------------------------------------------------------------


async def test_summarize_returns_narrative(test_client: AsyncClient):
    """GET /api/engram/summarize returns a narrative summary."""
    with patch(
        "engram.api.routes.engram.generate",
        new_callable=AsyncMock,
        return_value="I am a thoughtful person who loves technology.",
    ):
        resp = await test_client.get("/api/engram/summarize")
    assert resp.status_code == 200
    body = resp.json()
    assert "summary" in body
    assert isinstance(body["summary"], str)
    assert len(body["summary"]) > 0


# ---------------------------------------------------------------------------
# POST /api/engram/simulate
# ---------------------------------------------------------------------------


async def test_simulate_returns_decision(test_client: AsyncClient):
    """POST /api/engram/simulate returns a simulated decision."""
    with patch(
        "engram.api.routes.engram.generate",
        new_callable=AsyncMock,
        return_value="I would choose option A because...",
    ):
        resp = await test_client.post(
            "/api/engram/simulate",
            json={"scenario": "Should I switch to a new programming language?"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "decision" in body
    assert isinstance(body["decision"], str)


async def test_simulate_requires_scenario(test_client: AsyncClient):
    """POST /api/engram/simulate returns 422 without scenario."""
    resp = await test_client.post("/api/engram/simulate", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/engram/compare
# ---------------------------------------------------------------------------


async def test_compare_returns_analysis(test_client: AsyncClient):
    """POST /api/engram/compare returns a comparison analysis."""
    with patch(
        "engram.api.routes.engram.generate",
        new_callable=AsyncMock,
        return_value="You generally agree with this stance because...",
    ):
        resp = await test_client.post(
            "/api/engram/compare",
            json={"topic": "remote work", "stance": "It improves productivity"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "analysis" in body
    assert isinstance(body["analysis"], str)


async def test_compare_requires_fields(test_client: AsyncClient):
    """POST /api/engram/compare returns 422 without required fields."""
    resp = await test_client.post("/api/engram/compare", json={"topic": "test"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/engram/explain-belief/{id}
# ---------------------------------------------------------------------------


async def test_explain_belief_not_found(test_client: AsyncClient):
    """GET /api/engram/explain-belief/{id} returns 404 for unknown belief."""
    import uuid

    fake_id = uuid.uuid4()
    resp = await test_client.get(f"/api/engram/explain-belief/{fake_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/engram/export
# ---------------------------------------------------------------------------


async def test_export_empty_engram(test_client: AsyncClient):
    """POST /api/engram/export with no data returns valid structure."""
    resp = await test_client.post("/api/engram/export")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "1.0"
    assert "exported_at" in body
    assert "profile" in body
    assert isinstance(body["memories"], list)
    assert isinstance(body["beliefs"], list)
    assert isinstance(body["preferences"], list)
    assert isinstance(body["photos"], list)


async def test_export_with_data(test_client: AsyncClient):
    """POST /api/engram/export with data returns populated JSON."""
    # Create a belief
    await test_client.post(
        "/api/identity/beliefs",
        json={"topic": "export-test-topic", "stance": "strongly for", "confidence": 0.85},
    )
    # Create a preference
    await test_client.post(
        "/api/identity/preferences",
        json={"category": "export-test-cat", "value": "high", "strength": 0.7},
    )
    # Create a style
    await test_client.put(
        "/api/identity/style",
        json={"tone": "casual", "humor_level": 0.6},
    )

    resp = await test_client.post("/api/engram/export")
    assert resp.status_code == 200
    body = resp.json()

    assert body["version"] == "1.0"
    assert len(body["beliefs"]) >= 1
    # Find our specific belief
    export_belief = [b for b in body["beliefs"] if b["topic"] == "export-test-topic"]
    assert len(export_belief) == 1
    assert export_belief[0]["stance"] == "strongly for"
    assert export_belief[0]["confidence"] == 0.85

    assert len(body["preferences"]) >= 1
    export_pref = [p for p in body["preferences"] if p["category"] == "export-test-cat"]
    assert len(export_pref) == 1
    assert export_pref[0]["value"] == "high"

    assert body["style_profile"] is not None
    assert body["style_profile"]["tone"] == "casual"


async def test_import_engram(test_client: AsyncClient):
    """POST /api/engram/import creates data from export payload."""
    payload = {
        "version": "1.0",
        "exported_at": "2026-03-22T12:00:00Z",
        "profile": {"name": "imported-user", "description": "An imported profile"},
        "memories": [
            {
                "content": "I love hiking in the mountains.",
                "intent": "statement",
                "meaning": "outdoor enthusiasm",
                "source": "import",
                "authorship": "self",
                "importance_score": 0.8,
                "confidence": 0.9,
                "reinforcement_count": 2,
                "status": "active",
                "visibility": "active",
                "topics": ["hiking"],
                "people": [{"name": "Alice", "relationship_type": "friend"}],
            }
        ],
        "beliefs": [
            {
                "topic": "import-test-nature",
                "stance": "nature is healing",
                "nuance": "especially forests",
                "confidence": 0.95,
                "source": "import",
            }
        ],
        "preferences": [
            {
                "category": "import-test-outdoor",
                "value": "hiking",
                "strength": 0.9,
                "source": "import",
            }
        ],
        "style_profile": {
            "tone": "warm",
            "humor_level": 0.4,
            "verbosity": 0.6,
            "formality": 0.3,
        },
        "photos": [],
    }

    resp = await test_client.post("/api/engram/import", json=payload)
    assert resp.status_code == 200
    body = resp.json()

    assert body["memories_imported"] == 1
    assert body["beliefs_imported"] == 1
    assert body["preferences_imported"] == 1
    assert body["style_imported"] is True
    assert body["topics_linked"] == 1
    assert body["people_linked"] == 1


async def test_export_import_roundtrip(test_client: AsyncClient):
    """Export then import produces matching data."""
    # Set up some unique data for the roundtrip
    await test_client.post(
        "/api/identity/beliefs",
        json={
            "topic": "roundtrip-belief",
            "stance": "test stance",
            "confidence": 0.77,
        },
    )
    await test_client.post(
        "/api/identity/preferences",
        json={"category": "roundtrip-pref", "value": "test-value", "strength": 0.55},
    )
    await test_client.put(
        "/api/identity/style",
        json={"tone": "formal", "formality": 0.9},
    )

    # Export
    export_resp = await test_client.post("/api/engram/export")
    assert export_resp.status_code == 200
    export_data = export_resp.json()

    # Import the exported data
    import_resp = await test_client.post("/api/engram/import", json=export_data)
    assert import_resp.status_code == 200
    import_body = import_resp.json()

    # Verify import counts match export data
    assert import_body["beliefs_imported"] == len(export_data["beliefs"])
    assert import_body["preferences_imported"] == len(export_data["preferences"])
    if export_data["style_profile"]:
        assert import_body["style_imported"] is True
