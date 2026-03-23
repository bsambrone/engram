"""Tests for the Facebook JSON export parser."""

import json
import tempfile
from pathlib import Path

import pytest

from engram.ingestion.parsers.base import ExportParser
from engram.ingestion.parsers.facebook import FacebookExportParser


@pytest.fixture
def parser() -> FacebookExportParser:
    return FacebookExportParser()


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


async def test_facebook_parser_implements_protocol():
    """FacebookExportParser satisfies the ExportParser protocol."""
    assert isinstance(FacebookExportParser(), ExportParser)


# ------------------------------------------------------------------
# validate()
# ------------------------------------------------------------------


async def test_validate_with_posts_dir(parser: FacebookExportParser, tmp_dir: Path):
    """validate returns True when posts/ directory exists."""
    (tmp_dir / "posts").mkdir()
    assert parser.validate(tmp_dir) is True


async def test_validate_with_messages_dir(parser: FacebookExportParser, tmp_dir: Path):
    """validate returns True when messages/ directory exists."""
    (tmp_dir / "messages").mkdir()
    assert parser.validate(tmp_dir) is True


async def test_validate_with_nested_activity(parser: FacebookExportParser, tmp_dir: Path):
    """validate returns True for your_facebook_activity/ wrapper."""
    (tmp_dir / "your_facebook_activity" / "posts").mkdir(parents=True)
    assert parser.validate(tmp_dir) is True


async def test_validate_empty_directory(parser: FacebookExportParser, tmp_dir: Path):
    """validate returns False for an empty directory."""
    assert parser.validate(tmp_dir) is False


async def test_validate_non_directory(parser: FacebookExportParser, tmp_dir: Path):
    """validate returns False for a file path."""
    f = tmp_dir / "file.txt"
    f.write_text("not a dir")
    assert parser.validate(f) is False


# ------------------------------------------------------------------
# parse() - posts
# ------------------------------------------------------------------


async def test_parse_posts(parser: FacebookExportParser, tmp_dir: Path):
    """Posts are parsed with correct source and authorship."""
    posts_dir = tmp_dir / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {
            "timestamp": 1704067200,
            "data": [{"post": "My first Facebook post!"}],
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "facebook"
    assert doc.authorship == "user_authored"
    assert doc.content == "My first Facebook post!"
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2024


async def test_parse_post_empty_skipped(parser: FacebookExportParser, tmp_dir: Path):
    """Posts with no text are skipped."""
    posts_dir = tmp_dir / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {"timestamp": 1704067200, "data": [{"post": ""}]},
        {"timestamp": 1704067200, "data": []},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


async def test_parse_post_direct_text_key(parser: FacebookExportParser, tmp_dir: Path):
    """Posts with a direct 'text' key are parsed."""
    posts_dir = tmp_dir / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {"timestamp": 1704067200, "text": "Direct text content"},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "Direct text content"


# ------------------------------------------------------------------
# parse() - comments
# ------------------------------------------------------------------


async def test_parse_comments(parser: FacebookExportParser, tmp_dir: Path):
    """Comments are parsed as user_authored."""
    comments_dir = tmp_dir / "comments_and_reactions"
    _write_json(comments_dir / "comments.json", [
        {
            "timestamp": 1704153600,
            "data": [{"comment": {"comment": "Nice photo!"}}],
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "facebook"
    assert doc.authorship == "user_authored"
    assert doc.content == "Nice photo!"


async def test_parse_comment_empty_skipped(parser: FacebookExportParser, tmp_dir: Path):
    """Comments with empty text are skipped."""
    comments_dir = tmp_dir / "comments_and_reactions"
    _write_json(comments_dir / "comments.json", [
        {"timestamp": 1704153600, "data": [{"comment": {"comment": ""}}]},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


# ------------------------------------------------------------------
# parse() - messages
# ------------------------------------------------------------------


async def test_parse_messages(parser: FacebookExportParser, tmp_dir: Path):
    """Messages are parsed as 'received'."""
    inbox_dir = tmp_dir / "messages" / "inbox" / "JohnDoe_abc123"
    _write_json(inbox_dir / "message_1.json", {
        "messages": [
            {
                "sender_name": "John Doe",
                "content": "Hey, how are you?",
                "timestamp_ms": 1704067200000,
            },
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "facebook"
    assert doc.authorship == "received"
    assert doc.content == "Hey, how are you?"
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2024


async def test_parse_message_empty_skipped(parser: FacebookExportParser, tmp_dir: Path):
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


async def test_encoding_fix_posts(parser: FacebookExportParser, tmp_dir: Path):
    """Facebook's UTF-8-as-latin-1 encoding is corrected in posts."""
    # "caf\u00c3\u00a9" is "cafe\u0301" encoded as latin-1 bytes of UTF-8 "cafe\u0301"
    mangled = "caf\u00c3\u00a9"  # This is "cafe" with UTF-8 bytes read as latin-1
    posts_dir = tmp_dir / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {"timestamp": 1704067200, "data": [{"post": mangled}]},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "caf\u00e9"  # Properly decoded


async def test_encoding_fix_messages(parser: FacebookExportParser, tmp_dir: Path):
    """Facebook's encoding quirk is corrected in messages."""
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


async def test_timestamp_unix_seconds(parser: FacebookExportParser, tmp_dir: Path):
    """timestamp field as unix seconds is parsed."""
    posts_dir = tmp_dir / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {"timestamp": 1704067200, "data": [{"post": "ts test"}]},
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024


async def test_timestamp_ms(parser: FacebookExportParser, tmp_dir: Path):
    """timestamp_ms field (milliseconds) is parsed."""
    inbox_dir = tmp_dir / "messages" / "inbox" / "Person_abc"
    _write_json(inbox_dir / "message_1.json", {
        "messages": [
            {"sender_name": "Person", "content": "hi", "timestamp_ms": 1704067200000},
        ],
    })
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024


# ------------------------------------------------------------------
# Nested activity directory
# ------------------------------------------------------------------


async def test_parse_nested_activity_dir(parser: FacebookExportParser, tmp_dir: Path):
    """Content under your_facebook_activity/ is also discovered."""
    posts_dir = tmp_dir / "your_facebook_activity" / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {"timestamp": 1704067200, "data": [{"post": "Nested post"}]},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "Nested post"


# ------------------------------------------------------------------
# Combined parsing
# ------------------------------------------------------------------


async def test_parse_all_types_combined(parser: FacebookExportParser, tmp_dir: Path):
    """Posts, comments, and messages are all combined."""
    _write_json(tmp_dir / "posts" / "posts.json", [
        {"timestamp": 100, "data": [{"post": "A post"}]},
    ])
    _write_json(tmp_dir / "comments_and_reactions" / "comments.json", [
        {"timestamp": 200, "data": [{"comment": {"comment": "A comment"}}]},
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
    assert "A comment" in contents
    assert "A message" in contents
