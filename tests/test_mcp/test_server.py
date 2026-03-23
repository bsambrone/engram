"""Tests for the MCP server tool definitions and call handlers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engram.mcp.server import TOOL_NAMES, call_tool, list_tools

# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tools_returns_all_nine():
    """list_tools() must return exactly 9 tools with correct names."""
    tools = await list_tools()
    assert len(tools) == 9
    names = {t.name for t in tools}
    assert names == set(TOOL_NAMES)


@pytest.mark.asyncio
async def test_list_tools_have_descriptions():
    """Every tool should have a non-empty description."""
    tools = await list_tools()
    for tool in tools:
        assert tool.description, f"Tool {tool.name} has no description"


@pytest.mark.asyncio
async def test_list_tools_have_input_schemas():
    """Every tool should have an inputSchema dict with at least 'type'."""
    tools = await list_tools()
    for tool in tools:
        assert isinstance(tool.inputSchema, dict)
        assert tool.inputSchema.get("type") == "object"


# ---------------------------------------------------------------------------
# call_tool: answer_as_self
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_answer_as_self():
    """answer_as_self should call ask_engram and return a TextContent result."""
    fake_response = MagicMock()
    fake_response.answer = "I think Python is great."
    fake_response.confidence = 0.85
    fake_response.caveats = []

    mock_session = AsyncMock()

    with (
        patch("engram.mcp.server.async_session") as mock_factory,
        patch("engram.mcp.server.ask_engram", new_callable=AsyncMock) as mock_ask,
    ):
        # Make async context manager return the mock session
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_ask.return_value = fake_response

        result = await call_tool("answer_as_self", {"query": "What do you think of Python?"})

    assert len(result) == 1
    assert result[0].type == "text"
    assert "Python is great" in result[0].text
    mock_ask.assert_awaited_once()
    # Verify is_owner=False for shared access
    _, kwargs = mock_ask.call_args
    assert kwargs.get("is_owner") is False


# ---------------------------------------------------------------------------
# call_tool: list_topics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_list_topics():
    """list_topics should query Topic table and return formatted results."""
    mock_session = AsyncMock()

    # Create fake topic results
    fake_topic_1 = MagicMock()
    fake_topic_1.name = "programming"
    fake_topic_1.id = uuid.uuid4()

    fake_topic_2 = MagicMock()
    fake_topic_2.name = "cooking"
    fake_topic_2.id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.all.return_value = [("programming", 5), ("cooking", 3)]

    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("engram.mcp.server.async_session") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await call_tool("list_topics", {})

    assert len(result) == 1
    assert "programming" in result[0].text
    assert "cooking" in result[0].text


# ---------------------------------------------------------------------------
# call_tool: search_memories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_search_memories():
    """search_memories should embed the query and search via MemoryService."""
    mock_session = AsyncMock()

    fake_memory = MagicMock()
    fake_memory.content = "I love hiking in the mountains."
    fake_memory.intent = "personal"
    fake_memory.confidence = 0.9
    fake_memory.timestamp = datetime(2024, 1, 15, tzinfo=timezone.utc)

    with (
        patch("engram.mcp.server.async_session") as mock_factory,
        patch("engram.mcp.server.embed_texts", new_callable=AsyncMock) as mock_embed,
        patch("engram.mcp.server.MemoryService") as mock_svc_cls,
    ):
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_embed.return_value = [[0.1] * 1536]

        mock_svc = AsyncMock()
        mock_svc.remember.return_value = [fake_memory]
        mock_svc_cls.return_value = mock_svc

        result = await call_tool("search_memories", {"query": "hiking"})

    assert len(result) == 1
    assert "hiking" in result[0].text
    mock_embed.assert_awaited_once_with(["hiking"])
    mock_svc.remember.assert_awaited_once()


# ---------------------------------------------------------------------------
# call_tool: get_beliefs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_get_beliefs():
    """get_beliefs should return beliefs via identity service."""
    mock_session = AsyncMock()

    fake_profile = MagicMock()
    fake_profile.id = uuid.uuid4()

    fake_identity = {
        "beliefs": [
            {
                "id": str(uuid.uuid4()),
                "topic": "technology",
                "stance": "AI is transformative",
                "nuance": "but needs regulation",
                "confidence": 0.9,
                "source": "inferred",
            }
        ],
        "preferences": [],
        "style": None,
    }

    with (
        patch("engram.mcp.server.async_session") as mock_factory,
        patch("engram.mcp.server.IdentityService") as mock_svc_cls,
    ):
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_svc = AsyncMock()
        mock_svc.get_or_create_default_profile.return_value = fake_profile
        mock_svc.get_full_identity.return_value = fake_identity
        mock_svc_cls.return_value = mock_svc

        result = await call_tool("get_beliefs", {})

    assert len(result) == 1
    assert "technology" in result[0].text
    assert "AI is transformative" in result[0].text


# ---------------------------------------------------------------------------
# call_tool: unknown tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_unknown_tool():
    """Calling an unknown tool should return an error message."""
    result = await call_tool("nonexistent_tool", {})
    assert len(result) == 1
    assert "Unknown tool" in result[0].text


# ---------------------------------------------------------------------------
# call_tool: summarize_self
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_summarize_self():
    """summarize_self should get identity and call generate."""
    mock_session = AsyncMock()

    fake_profile = MagicMock()
    fake_profile.id = uuid.uuid4()
    fake_profile.name = "Alice"

    fake_identity = {
        "beliefs": [{"topic": "art", "stance": "essential", "confidence": 0.8}],
        "preferences": [{"category": "music", "value": "jazz", "strength": 0.9}],
        "style": {"tone": "warm", "humor_level": 0.7},
    }

    with (
        patch("engram.mcp.server.async_session") as mock_factory,
        patch("engram.mcp.server.IdentityService") as mock_svc_cls,
        patch("engram.mcp.server.generate", new_callable=AsyncMock) as mock_gen,
    ):
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_svc = AsyncMock()
        mock_svc.get_or_create_default_profile.return_value = fake_profile
        mock_svc.get_full_identity.return_value = fake_identity
        mock_svc_cls.return_value = mock_svc

        mock_gen.return_value = "I am Alice, an art lover who enjoys jazz."

        result = await call_tool("summarize_self", {})

    assert len(result) == 1
    assert "Alice" in result[0].text
    mock_gen.assert_awaited_once()


# ---------------------------------------------------------------------------
# call_tool: simulate_decision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_simulate_decision():
    """simulate_decision should frame scenario and call ask_engram."""
    fake_response = MagicMock()
    fake_response.answer = "I would choose option A."
    fake_response.confidence = 0.7
    fake_response.caveats = []

    mock_session = AsyncMock()

    with (
        patch("engram.mcp.server.async_session") as mock_factory,
        patch("engram.mcp.server.ask_engram", new_callable=AsyncMock) as mock_ask,
    ):
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_ask.return_value = fake_response

        result = await call_tool(
            "simulate_decision", {"scenario": "Should I take the new job?"}
        )

    assert len(result) == 1
    assert "option A" in result[0].text
    mock_ask.assert_awaited_once()
    # The query should include the scenario framing
    call_args = mock_ask.call_args
    assert "new job" in call_args[1].get("query", call_args[0][1] if len(call_args[0]) > 1 else "")


# ---------------------------------------------------------------------------
# CLI mcp command
# ---------------------------------------------------------------------------


def test_mcp_cli_command_calls_main():
    """Verify the mcp CLI command calls server.main via asyncio.run."""
    from click.testing import CliRunner

    from engram.cli import cli

    with patch("engram.cli.asyncio") as mock_asyncio:
        runner = CliRunner()
        result = runner.invoke(cli, ["mcp"])
        assert result.exit_code == 0
        mock_asyncio.run.assert_called_once()
