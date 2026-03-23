"""Tests for the Instagram JSON export parser."""

import json
import tempfile
from pathlib import Path

import pytest

from engram.ingestion.parsers.base import ExportParser
from engram.ingestion.parsers.instagram import InstagramExportParser


@pytest.fixture
def parser() -> InstagramExportParser:
    return InstagramExportParser(user_display_name="Bill Sambrone")


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


async def test_validate_with_media_dir(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns True when your_instagram_activity/media/ exists."""
    (tmp_dir / "your_instagram_activity" / "media").mkdir(parents=True)
    assert parser.validate(tmp_dir) is True


async def test_validate_with_comments_dir(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns True when your_instagram_activity/comments/ exists."""
    (tmp_dir / "your_instagram_activity" / "comments").mkdir(parents=True)
    assert parser.validate(tmp_dir) is True


async def test_validate_with_messages_dir(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns True when your_instagram_activity/messages/ exists."""
    (tmp_dir / "your_instagram_activity" / "messages").mkdir(parents=True)
    assert parser.validate(tmp_dir) is True


async def test_validate_empty_directory(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns False for an empty directory."""
    assert parser.validate(tmp_dir) is False


async def test_validate_non_directory(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns False for a file path."""
    f = tmp_dir / "file.txt"
    f.write_text("not a dir")
    assert parser.validate(f) is False


async def test_validate_without_activity_dir(parser: InstagramExportParser, tmp_dir: Path):
    """validate returns False when your_instagram_activity/ is missing."""
    (tmp_dir / "random_dir").mkdir()
    assert parser.validate(tmp_dir) is False


# ------------------------------------------------------------------
# parse() - posts  (your_instagram_activity/media/posts_*.json)
# ------------------------------------------------------------------


async def test_parse_posts(parser: InstagramExportParser, tmp_dir: Path):
    """Posts are parsed with correct source and authorship."""
    media_dir = tmp_dir / "your_instagram_activity" / "media"
    _write_json(media_dir / "posts_1.json", [
        {
            "media": [{
                "uri": "media/posts/202510/photo.jpg",
                "creation_timestamp": 1704067200,
                "title": "Beautiful sunset today!",
            }],
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


async def test_parse_post_empty_title_skipped(parser: InstagramExportParser, tmp_dir: Path):
    """Posts with no title are skipped."""
    media_dir = tmp_dir / "your_instagram_activity" / "media"
    _write_json(media_dir / "posts_1.json", [
        {"media": [{"uri": "photo.jpg", "creation_timestamp": 1704067200, "title": ""}]},
        {"media": [{"uri": "photo2.jpg", "creation_timestamp": 1704067200}]},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


async def test_parse_multiple_post_files(parser: InstagramExportParser, tmp_dir: Path):
    """Multiple posts_N.json files are all parsed."""
    media_dir = tmp_dir / "your_instagram_activity" / "media"
    _write_json(media_dir / "posts_1.json", [
        {"media": [{"title": "Post one", "creation_timestamp": 100}]},
    ])
    _write_json(media_dir / "posts_2.json", [
        {"media": [{"title": "Post two", "creation_timestamp": 200}]},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 2
    contents = {d.content for d in docs}
    assert "Post one" in contents
    assert "Post two" in contents


# ------------------------------------------------------------------
# parse() - comments  (your_instagram_activity/comments/post_comments_*.json)
# ------------------------------------------------------------------


async def test_parse_comments(parser: InstagramExportParser, tmp_dir: Path):
    """Comments with string_map_data format are parsed."""
    comments_dir = tmp_dir / "your_instagram_activity" / "comments"
    _write_json(comments_dir / "post_comments_1.json", [
        {
            "string_map_data": {
                "Comment": {"value": "Great photo!"},
                "Media Owner": {"value": "billsambrone"},
                "Time": {"timestamp": 1591846694},
            },
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "instagram"
    assert doc.authorship == "user_authored"
    assert doc.content == "Great photo!"
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2020


async def test_parse_comment_empty_skipped(parser: InstagramExportParser, tmp_dir: Path):
    """Comments with empty value are skipped."""
    comments_dir = tmp_dir / "your_instagram_activity" / "comments"
    _write_json(comments_dir / "post_comments_1.json", [
        {
            "string_map_data": {
                "Comment": {"value": ""},
                "Time": {"timestamp": 1591846694},
            },
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


# ------------------------------------------------------------------
# parse() - messages
# ------------------------------------------------------------------


async def test_parse_messages_user_authored(parser: InstagramExportParser, tmp_dir: Path):
    """Messages from the user are tagged as 'user_authored'."""
    inbox_dir = tmp_dir / "your_instagram_activity" / "messages" / "inbox" / "JaneDoe_123"
    _write_json(inbox_dir / "message_1.json", {
        "participants": [{"name": "Jane Doe"}, {"name": "Bill Sambrone"}],
        "messages": [
            {
                "sender_name": "Bill Sambrone",
                "timestamp_ms": 1704067200000,
                "content": "Hey, how's it going?",
            },
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "instagram"
    assert doc.authorship == "user_authored"
    assert doc.content == "Hey, how's it going?"
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2024


async def test_parse_messages_received(parser: InstagramExportParser, tmp_dir: Path):
    """Messages from others are tagged as 'received'."""
    inbox_dir = tmp_dir / "your_instagram_activity" / "messages" / "inbox" / "JaneDoe_123"
    _write_json(inbox_dir / "message_1.json", {
        "participants": [{"name": "Jane Doe"}, {"name": "Bill Sambrone"}],
        "messages": [
            {
                "sender_name": "Jane Doe",
                "timestamp_ms": 1704067200000,
                "content": "Love your photos!",
            },
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].authorship == "received"


async def test_parse_message_requests(parser: InstagramExportParser, tmp_dir: Path):
    """Messages from message_requests/ are also parsed."""
    req_dir = (
        tmp_dir / "your_instagram_activity" / "messages" / "message_requests" / "Spammer_456"
    )
    _write_json(req_dir / "message_1.json", {
        "participants": [{"name": "Spammer"}],
        "messages": [
            {
                "sender_name": "Spammer",
                "timestamp_ms": 1704067200000,
                "content": "Follow me!",
            },
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].authorship == "received"
    assert docs[0].content == "Follow me!"


async def test_parse_message_empty_skipped(parser: InstagramExportParser, tmp_dir: Path):
    """Messages with empty content are skipped."""
    inbox_dir = tmp_dir / "your_instagram_activity" / "messages" / "inbox" / "Empty_convo"
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
    media_dir = tmp_dir / "your_instagram_activity" / "media"
    _write_json(media_dir / "posts_1.json", [
        {"media": [{"title": mangled, "creation_timestamp": 1704067200}]},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "caf\u00e9"


async def test_encoding_fix_messages(parser: InstagramExportParser, tmp_dir: Path):
    """Instagram's encoding quirk is corrected in messages."""
    mangled = "caf\u00c3\u00a9"
    inbox_dir = tmp_dir / "your_instagram_activity" / "messages" / "inbox" / "Friend_xyz"
    _write_json(inbox_dir / "message_1.json", {
        "messages": [
            {"sender_name": "Friend", "content": mangled, "timestamp_ms": 1704067200000},
        ],
    })
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "caf\u00e9"


async def test_encoding_fix_comments(parser: InstagramExportParser, tmp_dir: Path):
    """Instagram's encoding quirk is corrected in comments."""
    mangled = "caf\u00c3\u00a9"
    comments_dir = tmp_dir / "your_instagram_activity" / "comments"
    _write_json(comments_dir / "post_comments_1.json", [
        {
            "string_map_data": {
                "Comment": {"value": mangled},
                "Time": {"timestamp": 1704067200},
            },
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].content == "caf\u00e9"


# ------------------------------------------------------------------
# Timestamp parsing
# ------------------------------------------------------------------


async def test_timestamp_creation_timestamp(parser: InstagramExportParser, tmp_dir: Path):
    """creation_timestamp (unix seconds) in posts is parsed."""
    media_dir = tmp_dir / "your_instagram_activity" / "media"
    _write_json(media_dir / "posts_1.json", [
        {"media": [{"title": "ts test", "creation_timestamp": 1704067200}]},
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024


async def test_timestamp_ms(parser: InstagramExportParser, tmp_dir: Path):
    """timestamp_ms (milliseconds) in messages is parsed."""
    inbox_dir = tmp_dir / "your_instagram_activity" / "messages" / "inbox" / "Person_abc"
    _write_json(inbox_dir / "message_1.json", {
        "messages": [
            {"sender_name": "Person", "content": "hi", "timestamp_ms": 1704067200000},
        ],
    })
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024


async def test_timestamp_missing_post(parser: InstagramExportParser, tmp_dir: Path):
    """Missing timestamp in posts results in None."""
    media_dir = tmp_dir / "your_instagram_activity" / "media"
    _write_json(media_dir / "posts_1.json", [
        {"media": [{"title": "no timestamp"}]},
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is None


# ------------------------------------------------------------------
# Combined parsing
# ------------------------------------------------------------------


async def test_parse_all_types_combined(parser: InstagramExportParser, tmp_dir: Path):
    """Posts, comments, and messages are all combined."""
    activity = tmp_dir / "your_instagram_activity"
    _write_json(activity / "media" / "posts_1.json", [
        {"media": [{"title": "A post", "creation_timestamp": 100}]},
    ])
    _write_json(activity / "comments" / "post_comments_1.json", [
        {
            "string_map_data": {
                "Comment": {"value": "A comment"},
                "Time": {"timestamp": 200},
            },
        },
    ])
    _write_json(activity / "messages" / "inbox" / "Chat_1" / "message_1.json", {
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
