"""Tests for the Instagram JSON export parser."""

import json
import tempfile
from pathlib import Path

import pytest

from engram.ingestion.parsers.base import ExportParser
from engram.ingestion.parsers.instagram import InstagramExportParser


@pytest.fixture
def parser() -> InstagramExportParser:
    return InstagramExportParser()


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _write_json(path: Path, data: list | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ------------------------------------------------------------------
# Protocol conformance
# ------------------------------------------------------------------


async def test_instagram_parser_implements_protocol():
    """InstagramExportParser satisfies the ExportParser protocol."""
    assert isinstance(InstagramExportParser(), ExportParser)


# ------------------------------------------------------------------
# validate()
# ------------------------------------------------------------------


async def test_validate_with_content_dir(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns True when content/ directory exists."""
    (tmp_dir / "content").mkdir()
    assert parser.validate(tmp_dir) is True


async def test_validate_with_messages_dir(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns True when messages/ directory exists."""
    (tmp_dir / "messages").mkdir()
    assert parser.validate(tmp_dir) is True


async def test_validate_with_nested_activity(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns True for your_instagram_activity/ wrapper."""
    (tmp_dir / "your_instagram_activity" / "content").mkdir(parents=True)
    assert parser.validate(tmp_dir) is True


async def test_validate_empty_directory(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns False for an empty directory."""
    assert parser.validate(tmp_dir) is False


async def test_validate_non_directory(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns False for a file path."""
    f = tmp_dir / "file.txt"
    f.write_text("not a dir")
    assert parser.validate(f) is False


# ------------------------------------------------------------------
# parse() - content (posts)
# ------------------------------------------------------------------


async def test_parse_posts(parser: InstagramExportParser, tmp_dir: Path):
    """Posts are parsed with correct source and authorship."""
    content_dir = tmp_dir / "content"
    _write_json(content_dir / "posts_1.json", [
        {
            "title": "Beautiful sunset today!",
            "creation_timestamp": 1704067200,
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "instagram"
    assert doc.authorship == "user_authored"
    assert doc.content == "Beautiful sunset today!"
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2024


async def test_parse_post_with_caption(parser: InstagramExportParser, tmp_dir: Path):
    """Posts with a 'caption' field are parsed."""
    content_dir = tmp_dir / "content"
    _write_json(content_dir / "posts_1.json", [
        {"caption": "Caption text here", "creation_timestamp": 1704067200},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "Caption text here"


async def test_parse_stories(parser: InstagramExportParser, tmp_dir: Path):
    """Stories with text are parsed as user_authored."""
    content_dir = tmp_dir / "content"
    _write_json(content_dir / "stories.json", [
        {"title": "Story caption", "creation_timestamp": 1704153600},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].authorship == "user_authored"
    assert docs[0].content == "Story caption"


async def test_parse_post_empty_skipped(parser: InstagramExportParser, tmp_dir: Path):
    """Posts with no text content are skipped."""
    content_dir = tmp_dir / "content"
    _write_json(content_dir / "posts_1.json", [
        {"title": "", "creation_timestamp": 1704067200},
        {"creation_timestamp": 1704067200},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


# ------------------------------------------------------------------
# parse() - messages
# ------------------------------------------------------------------


async def test_parse_messages(parser: InstagramExportParser, tmp_dir: Path):
    """Messages are parsed as 'received'."""
    inbox_dir = tmp_dir / "messages" / "inbox" / "JaneDoe_20240101"
    _write_json(inbox_dir / "message_1.json", {
        "messages": [
            {
                "sender_name": "Jane Doe",
                "content": "Love your photos!",
                "timestamp_ms": 1704067200000,
            },
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "instagram"
    assert doc.authorship == "received"
    assert doc.content == "Love your photos!"
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2024


async def test_parse_message_empty_skipped(parser: InstagramExportParser, tmp_dir: Path):
    """Messages with empty content are skipped."""
    inbox_dir = tmp_dir / "messages" / "inbox" / "Empty_convo"
    _write_json(inbox_dir / "message_1.json", {
        "messages": [
            {"sender_name": "Nobody", "content": "", "timestamp_ms": 1704067200000},
            {"sender_name": "Nobody", "content": "   ", "timestamp_ms": 1704067200000},
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


# ------------------------------------------------------------------
# Encoding handling
# ------------------------------------------------------------------


async def test_encoding_fix_posts(parser: InstagramExportParser, tmp_dir: Path):
    """Instagram's UTF-8-as-latin-1 encoding is corrected in posts."""
    mangled = "caf\u00c3\u00a9"  # UTF-8 bytes of "cafe\u0301" read as latin-1
    content_dir = tmp_dir / "content"
    _write_json(content_dir / "posts_1.json", [
        {"title": mangled, "creation_timestamp": 1704067200},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "caf\u00e9"


async def test_encoding_fix_messages(parser: InstagramExportParser, tmp_dir: Path):
    """Instagram's encoding quirk is corrected in messages."""
    mangled = "caf\u00c3\u00a9"
    inbox_dir = tmp_dir / "messages" / "inbox" / "Friend_xyz"
    _write_json(inbox_dir / "message_1.json", {
        "messages": [
            {"sender_name": "Friend", "content": mangled, "timestamp_ms": 1704067200000},
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "caf\u00e9"


# ------------------------------------------------------------------
# Timestamp parsing
# ------------------------------------------------------------------


async def test_timestamp_creation_timestamp(parser: InstagramExportParser, tmp_dir: Path):
    """creation_timestamp (unix seconds) is parsed."""
    content_dir = tmp_dir / "content"
    _write_json(content_dir / "posts_1.json", [
        {"title": "ts test", "creation_timestamp": 1704067200},
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024


async def test_timestamp_ms(parser: InstagramExportParser, tmp_dir: Path):
    """timestamp_ms (milliseconds) is parsed."""
    inbox_dir = tmp_dir / "messages" / "inbox" / "Person_abc"
    _write_json(inbox_dir / "message_1.json", {
        "messages": [
            {"sender_name": "Person", "content": "hi", "timestamp_ms": 1704067200000},
        ],
    })
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024


async def test_timestamp_missing(parser: InstagramExportParser, tmp_dir: Path):
    """Missing timestamp results in None."""
    content_dir = tmp_dir / "content"
    _write_json(content_dir / "posts_1.json", [
        {"title": "no timestamp"},
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is None


# ------------------------------------------------------------------
# Nested activity directory
# ------------------------------------------------------------------


async def test_parse_nested_activity_dir(parser: InstagramExportParser, tmp_dir: Path):
    """Content under your_instagram_activity/ is also discovered."""
    content_dir = tmp_dir / "your_instagram_activity" / "content"
    _write_json(content_dir / "posts_1.json", [
        {"title": "Nested post", "creation_timestamp": 1704067200},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "Nested post"


# ------------------------------------------------------------------
# Combined parsing
# ------------------------------------------------------------------


async def test_parse_all_types_combined(parser: InstagramExportParser, tmp_dir: Path):
    """Posts, stories, and messages are all combined."""
    _write_json(tmp_dir / "content" / "posts_1.json", [
        {"title": "A post", "creation_timestamp": 100},
    ])
    _write_json(tmp_dir / "content" / "stories.json", [
        {"title": "A story", "creation_timestamp": 200},
    ])
    _write_json(tmp_dir / "messages" / "inbox" / "Chat_1" / "message_1.json", {
        "messages": [
            {"sender_name": "Pal", "content": "A message", "timestamp_ms": 300000},
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 3
    contents = {d.content for d in docs}
    assert "A post" in contents
    assert "A story" in contents
    assert "A message" in contents
