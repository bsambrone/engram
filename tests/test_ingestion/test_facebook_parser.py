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
    """validate returns True when your_facebook_activity/posts/ directory exists."""
    (tmp_dir / "your_facebook_activity" / "posts").mkdir(parents=True)
    assert parser.validate(tmp_dir) is True


async def test_validate_with_messages_dir(parser: FacebookExportParser, tmp_dir: Path):
    """validate returns True when your_facebook_activity/messages/ directory exists."""
    (tmp_dir / "your_facebook_activity" / "messages").mkdir(parents=True)
    assert parser.validate(tmp_dir) is True


async def test_validate_with_comments_dir(parser: FacebookExportParser, tmp_dir: Path):
    """validate returns True when your_facebook_activity/comments_and_reactions/ exists."""
    (tmp_dir / "your_facebook_activity" / "comments_and_reactions").mkdir(parents=True)
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
    posts_dir = tmp_dir / "your_facebook_activity" / "posts"
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
    posts_dir = tmp_dir / "your_facebook_activity" / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {"timestamp": 1704067200, "data": [{"post": ""}]},
        {"timestamp": 1704067200, "data": []},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


async def test_parse_post_direct_text_key(parser: FacebookExportParser, tmp_dir: Path):
    """Posts with a direct 'text' key are parsed."""
    posts_dir = tmp_dir / "your_facebook_activity" / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {"timestamp": 1704067200, "text": "Direct text content"},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "Direct text content"


async def test_parse_posts_with_tags(parser: FacebookExportParser, tmp_dir: Path):
    """Posts with tags extract people names."""
    posts_dir = tmp_dir / "your_facebook_activity" / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {
            "timestamp": 1704067200,
            "data": [{"post": "Great day!"}],
            "tags": [{"name": "John Smith"}, {"name": "Sarah Connor"}],
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert "John Smith" in docs[0].people
    assert "Sarah Connor" in docs[0].people


# ------------------------------------------------------------------
# parse() - comments
# ------------------------------------------------------------------


async def test_parse_comments_v2_format(parser: FacebookExportParser, tmp_dir: Path):
    """Comments wrapped in comments_v2 dict are parsed as user_authored."""
    comments_dir = tmp_dir / "your_facebook_activity" / "comments_and_reactions"
    _write_json(comments_dir / "comments.json", {
        "comments_v2": [
            {
                "timestamp": 1704153600,
                "data": [{"comment": {"comment": "Nice photo!", "author": "Bill Sambrone"}}],
                "title": "Bill Sambrone commented on Someone's post.",
            },
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "facebook"
    assert doc.authorship == "user_authored"
    assert doc.content == "Nice photo!"


async def test_parse_comments_list_format(parser: FacebookExportParser, tmp_dir: Path):
    """Comments as a plain list are also parsed."""
    comments_dir = tmp_dir / "your_facebook_activity" / "comments_and_reactions"
    _write_json(comments_dir / "comments.json", [
        {
            "timestamp": 1704153600,
            "data": [{"comment": {"comment": "Nice photo!"}}],
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "Nice photo!"


async def test_parse_comment_empty_skipped(parser: FacebookExportParser, tmp_dir: Path):
    """Comments with empty text are skipped."""
    comments_dir = tmp_dir / "your_facebook_activity" / "comments_and_reactions"
    _write_json(comments_dir / "comments.json", {
        "comments_v2": [
            {"timestamp": 1704153600, "data": [{"comment": {"comment": ""}}]},
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


# ------------------------------------------------------------------
# parse() - messages
# ------------------------------------------------------------------


async def test_parse_messages_user_authored(parser: FacebookExportParser, tmp_dir: Path):
    """Messages from the user are marked as user_authored."""
    inbox_dir = (
        tmp_dir / "your_facebook_activity" / "messages" / "inbox" / "JohnDoe_abc123"
    )
    _write_json(inbox_dir / "message_1.json", {
        "participants": [{"name": "John Doe"}, {"name": "Bill Sambrone"}],
        "messages": [
            {
                "sender_name": "Bill Sambrone",
                "content": "Hey John!",
                "timestamp_ms": 1704067200000,
            },
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "facebook"
    assert doc.authorship == "user_authored"
    assert doc.content == "Hey John!"
    assert doc.people == []  # user's own message — no external people


async def test_parse_messages_received(parser: FacebookExportParser, tmp_dir: Path):
    """Messages from others are marked as received with people set."""
    inbox_dir = (
        tmp_dir / "your_facebook_activity" / "messages" / "inbox" / "JohnDoe_abc123"
    )
    _write_json(inbox_dir / "message_1.json", {
        "participants": [{"name": "John Doe"}, {"name": "Bill Sambrone"}],
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
    assert doc.people == ["John Doe"]
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2024


async def test_parse_message_empty_skipped(parser: FacebookExportParser, tmp_dir: Path):
    """Messages with empty content are skipped."""
    inbox_dir = (
        tmp_dir / "your_facebook_activity" / "messages" / "inbox" / "Empty_convo"
    )
    _write_json(inbox_dir / "message_1.json", {
        "messages": [
            {"sender_name": "Nobody", "content": "", "timestamp_ms": 1704067200000},
            {"sender_name": "Nobody", "content": "   ", "timestamp_ms": 1704067200000},
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


async def test_parse_message_requests(parser: FacebookExportParser, tmp_dir: Path):
    """Messages in message_requests are also parsed."""
    req_dir = (
        tmp_dir / "your_facebook_activity" / "messages" / "message_requests" / "Req_1"
    )
    _write_json(req_dir / "message_1.json", {
        "participants": [{"name": "Stranger"}, {"name": "Bill Sambrone"}],
        "messages": [
            {
                "sender_name": "Stranger",
                "content": "Hello there",
                "timestamp_ms": 1704067200000,
            },
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "Hello there"
    assert docs[0].authorship == "received"


# ------------------------------------------------------------------
# Encoding handling
# ------------------------------------------------------------------


async def test_encoding_fix_posts(parser: FacebookExportParser, tmp_dir: Path):
    """Facebook's UTF-8-as-latin-1 encoding is corrected in posts."""
    mangled = "caf\u00c3\u00a9"
    posts_dir = tmp_dir / "your_facebook_activity" / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {"timestamp": 1704067200, "data": [{"post": mangled}]},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "caf\u00e9"


async def test_encoding_fix_messages(parser: FacebookExportParser, tmp_dir: Path):
    """Facebook's encoding quirk is corrected in messages."""
    mangled = "caf\u00c3\u00a9"
    inbox_dir = (
        tmp_dir / "your_facebook_activity" / "messages" / "inbox" / "Friend_xyz"
    )
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
    posts_dir = tmp_dir / "your_facebook_activity" / "posts"
    _write_json(posts_dir / "your_posts_1.json", [
        {"timestamp": 1704067200, "data": [{"post": "ts test"}]},
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024


async def test_timestamp_ms(parser: FacebookExportParser, tmp_dir: Path):
    """timestamp_ms field (milliseconds) is parsed."""
    inbox_dir = (
        tmp_dir / "your_facebook_activity" / "messages" / "inbox" / "Person_abc"
    )
    _write_json(inbox_dir / "message_1.json", {
        "messages": [
            {"sender_name": "Person", "content": "hi", "timestamp_ms": 1704067200000},
        ],
    })
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024


# ------------------------------------------------------------------
# Combined parsing
# ------------------------------------------------------------------


async def test_parse_all_types_combined(parser: FacebookExportParser, tmp_dir: Path):
    """Posts, comments, and messages are all combined."""
    activity = tmp_dir / "your_facebook_activity"
    _write_json(activity / "posts" / "posts.json", [
        {"timestamp": 100, "data": [{"post": "A post"}]},
    ])
    _write_json(activity / "comments_and_reactions" / "comments.json", {
        "comments_v2": [
            {"timestamp": 200, "data": [{"comment": {"comment": "A comment"}}]},
        ],
    })
    _write_json(activity / "messages" / "inbox" / "Chat_1" / "message_1.json", {
        "participants": [{"name": "Pal"}, {"name": "Bill Sambrone"}],
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
