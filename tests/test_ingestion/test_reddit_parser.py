"""Tests for the Reddit JSON export parser."""

import json
import tempfile
from pathlib import Path

import pytest

from engram.ingestion.parsers.base import ExportParser
from engram.ingestion.parsers.reddit import RedditExportParser


@pytest.fixture
def parser() -> RedditExportParser:
    return RedditExportParser(username="testuser")


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


async def test_reddit_parser_implements_protocol():
    """RedditExportParser satisfies the ExportParser protocol."""
    assert isinstance(RedditExportParser(), ExportParser)


# ------------------------------------------------------------------
# validate()
# ------------------------------------------------------------------


async def test_validate_with_posts_json(parser: RedditExportParser, tmp_dir: Path):
    """validate returns True when posts.json exists."""
    _write_json(tmp_dir / "posts.json", [])
    assert parser.validate(tmp_dir) is True


async def test_validate_with_comments_json(parser: RedditExportParser, tmp_dir: Path):
    """validate returns True when comments.json exists."""
    _write_json(tmp_dir / "comments.json", [])
    assert parser.validate(tmp_dir) is True


async def test_validate_with_saved_posts(parser: RedditExportParser, tmp_dir: Path):
    """validate returns True when saved_posts.json exists."""
    _write_json(tmp_dir / "saved_posts.json", [])
    assert parser.validate(tmp_dir) is True


async def test_validate_empty_directory(parser: RedditExportParser, tmp_dir: Path):
    """validate returns False for an empty directory."""
    assert parser.validate(tmp_dir) is False


async def test_validate_non_directory(parser: RedditExportParser, tmp_dir: Path):
    """validate returns False for a file path."""
    f = tmp_dir / "not_a_dir.txt"
    f.write_text("hello")
    assert parser.validate(f) is False


async def test_validate_nonexistent(parser: RedditExportParser, tmp_dir: Path):
    """validate returns False for a nonexistent path."""
    assert parser.validate(tmp_dir / "nope") is False


# ------------------------------------------------------------------
# parse() - posts
# ------------------------------------------------------------------


async def test_parse_posts(parser: RedditExportParser, tmp_dir: Path):
    """Posts are parsed with correct source, authorship, and content."""
    _write_json(tmp_dir / "posts.json", [
        {
            "title": "My first post",
            "selftext": "This is the body of my post.",
            "permalink": "/r/test/comments/abc123/my_first_post/",
            "created_utc": 1704067200,  # 2024-01-01 00:00:00 UTC
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "reddit"
    assert doc.authorship == "user_authored"
    assert "My first post" in doc.content
    assert "This is the body of my post." in doc.content
    assert doc.source_ref == "/r/test/comments/abc123/my_first_post/"
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2024


async def test_parse_post_title_only(parser: RedditExportParser, tmp_dir: Path):
    """Posts with only a title (no selftext) are still parsed."""
    _write_json(tmp_dir / "posts.json", [
        {
            "title": "Link post title",
            "selftext": "",
            "permalink": "/r/test/comments/xyz/",
            "created_utc": 1704067200,
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert "Link post title" in docs[0].content


async def test_parse_post_empty_skipped(parser: RedditExportParser, tmp_dir: Path):
    """Posts with no title and no body are skipped."""
    _write_json(tmp_dir / "posts.json", [
        {"title": "", "selftext": "", "permalink": "/r/empty/", "created_utc": 0},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


# ------------------------------------------------------------------
# parse() - comments
# ------------------------------------------------------------------


async def test_parse_comments(parser: RedditExportParser, tmp_dir: Path):
    """Comments are parsed with correct authorship."""
    _write_json(tmp_dir / "comments.json", [
        {
            "body": "Great post, thanks for sharing!",
            "permalink": "/r/test/comments/abc123/my_post/def456/",
            "created_utc": 1704153600,
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "reddit"
    assert doc.authorship == "user_authored"
    assert doc.content == "Great post, thanks for sharing!"
    assert doc.source_ref == "/r/test/comments/abc123/my_post/def456/"


async def test_parse_comment_empty_body_skipped(parser: RedditExportParser, tmp_dir: Path):
    """Comments with empty body are skipped."""
    _write_json(tmp_dir / "comments.json", [
        {"body": "", "permalink": "/r/empty/", "created_utc": 0},
        {"body": "   ", "permalink": "/r/whitespace/", "created_utc": 0},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


# ------------------------------------------------------------------
# parse() - saved content
# ------------------------------------------------------------------


async def test_parse_saved_posts_authorship(parser: RedditExportParser, tmp_dir: Path):
    """Saved posts are tagged as 'received'."""
    _write_json(tmp_dir / "saved_posts.json", [
        {
            "title": "Saved from someone else",
            "selftext": "Interesting content.",
            "permalink": "/r/other/comments/saved1/",
            "created_utc": 1704067200,
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].authorship == "received"


async def test_parse_saved_comments_authorship(parser: RedditExportParser, tmp_dir: Path):
    """Saved comments are tagged as 'received'."""
    _write_json(tmp_dir / "saved_comments.json", [
        {
            "body": "A saved comment from another user.",
            "permalink": "/r/other/comments/saved2/cmt1/",
            "created_utc": 1704067200,
        },
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert docs[0].authorship == "received"


# ------------------------------------------------------------------
# Timestamp parsing
# ------------------------------------------------------------------


async def test_timestamp_unix_int(parser: RedditExportParser, tmp_dir: Path):
    """created_utc as an integer unix timestamp is parsed."""
    _write_json(tmp_dir / "posts.json", [
        {"title": "ts test", "created_utc": 1704067200},
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024
    assert docs[0].timestamp.month == 1
    assert docs[0].timestamp.day == 1


async def test_timestamp_unix_string(parser: RedditExportParser, tmp_dir: Path):
    """created_utc as a string-encoded unix timestamp is parsed."""
    _write_json(tmp_dir / "posts.json", [
        {"title": "ts test", "created_utc": "1704067200"},
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024


async def test_timestamp_iso_string(parser: RedditExportParser, tmp_dir: Path):
    """created field as an ISO date string is parsed."""
    _write_json(tmp_dir / "posts.json", [
        {"title": "ts test", "created": "2024-06-15T10:30:00"},
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2024
    assert docs[0].timestamp.month == 6


async def test_timestamp_missing(parser: RedditExportParser, tmp_dir: Path):
    """Missing timestamp fields result in None."""
    _write_json(tmp_dir / "posts.json", [
        {"title": "no timestamp"},
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is None


# ------------------------------------------------------------------
# Multiple files combined
# ------------------------------------------------------------------


async def test_parse_multiple_files(parser: RedditExportParser, tmp_dir: Path):
    """Posts and comments from separate files are combined."""
    _write_json(tmp_dir / "posts.json", [
        {"title": "Post 1", "selftext": "Body 1", "permalink": "/p1/", "created_utc": 100},
        {"title": "Post 2", "selftext": "Body 2", "permalink": "/p2/", "created_utc": 200},
    ])
    _write_json(tmp_dir / "comments.json", [
        {"body": "Comment 1", "permalink": "/c1/", "created_utc": 300},
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 3
    sources = {d.source_ref for d in docs}
    assert "/p1/" in sources
    assert "/p2/" in sources
    assert "/c1/" in sources
