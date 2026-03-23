"""Tests for the Reddit CSV export parser."""

import csv
import tempfile
from pathlib import Path

import pytest

from engram.ingestion.parsers.base import ExportParser
from engram.ingestion.parsers.reddit import RedditExportParser


@pytest.fixture
def parser() -> RedditExportParser:
    return RedditExportParser()


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


_POST_HEADERS = ["id", "permalink", "date", "ip", "subreddit", "gildings", "title", "url", "body"]
_COMMENT_HEADERS = [
    "id", "permalink", "date", "ip", "subreddit", "gildings", "link", "parent", "body", "media",
]
_CHAT_HEADERS = [
    "message_id", "created_at", "updated_at", "username", "message",
    "thread_parent_message_id", "channel_url", "subreddit", "channel_name", "conversation_type",
]


# ------------------------------------------------------------------
# Protocol conformance
# ------------------------------------------------------------------


async def test_reddit_parser_implements_protocol():
    """RedditExportParser satisfies the ExportParser protocol."""
    assert isinstance(RedditExportParser(), ExportParser)


# ------------------------------------------------------------------
# validate()
# ------------------------------------------------------------------


async def test_validate_with_posts_csv(parser: RedditExportParser, tmp_dir: Path):
    """validate returns True when posts.csv exists."""
    _write_csv(tmp_dir / "posts.csv", _POST_HEADERS, [])
    assert parser.validate(tmp_dir) is True


async def test_validate_with_comments_csv(parser: RedditExportParser, tmp_dir: Path):
    """validate returns True when comments.csv exists."""
    _write_csv(tmp_dir / "comments.csv", _COMMENT_HEADERS, [])
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
    _write_csv(tmp_dir / "posts.csv", _POST_HEADERS, [
        ["abc123", "https://reddit.com/r/test/comments/abc123/my_first_post/",
         "2024-01-01 00:00:00 UTC", "", "test", "0", "My first post",
         "/r/test/comments/abc123/my_first_post/", "This is the body of my post."],
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "reddit"
    assert doc.authorship == "user_authored"
    assert "My first post" in doc.content
    assert "This is the body of my post." in doc.content
    assert doc.source_ref == "https://reddit.com/r/test/comments/abc123/my_first_post/"
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2024


async def test_parse_post_title_only(parser: RedditExportParser, tmp_dir: Path):
    """Posts with only a title (no body) are still parsed."""
    _write_csv(tmp_dir / "posts.csv", _POST_HEADERS, [
        ["xyz", "https://reddit.com/r/test/comments/xyz/", "2024-01-01 00:00:00 UTC",
         "", "test", "0", "Link post title", "/r/test/comments/xyz/", ""],
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    assert "Link post title" in docs[0].content


async def test_parse_post_empty_skipped(parser: RedditExportParser, tmp_dir: Path):
    """Posts with no title and no body are skipped."""
    _write_csv(tmp_dir / "posts.csv", _POST_HEADERS, [
        ["empty", "/r/empty/", "2024-01-01 00:00:00 UTC", "", "test", "0", "", "", ""],
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


# ------------------------------------------------------------------
# parse() - comments
# ------------------------------------------------------------------


async def test_parse_comments(parser: RedditExportParser, tmp_dir: Path):
    """Comments are parsed with correct authorship."""
    _write_csv(tmp_dir / "comments.csv", _COMMENT_HEADERS, [
        ["def456", "https://reddit.com/r/test/comments/abc123/my_post/def456/",
         "2024-01-02 00:00:00 UTC", "", "test", "0",
         "https://reddit.com/r/test/comments/abc123/my_post/", "",
         "Great post, thanks for sharing!", ""],
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "reddit"
    assert doc.authorship == "user_authored"
    assert doc.content == "Great post, thanks for sharing!"
    assert doc.source_ref == "https://reddit.com/r/test/comments/abc123/my_post/def456/"


async def test_parse_comment_empty_body_skipped(parser: RedditExportParser, tmp_dir: Path):
    """Comments with empty body are skipped."""
    _write_csv(tmp_dir / "comments.csv", _COMMENT_HEADERS, [
        ["e1", "/r/empty/", "2024-01-01 00:00:00 UTC", "", "test", "0", "", "", "", ""],
        ["e2", "/r/whitespace/", "2024-01-01 00:00:00 UTC", "", "test", "0", "", "", "   ", ""],
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


# ------------------------------------------------------------------
# parse() - chat history
# ------------------------------------------------------------------


async def test_parse_chat(parser: RedditExportParser, tmp_dir: Path):
    """Chat messages are parsed with correct authorship."""
    _write_csv(tmp_dir / "chat_history.csv", _CHAT_HEADERS, [
        ["msg1", "2024-06-15 10:30:00 UTC", "2024-06-15 10:30:00 UTC",
         "/u/testuser", "Hello from chat!", "", "", "", "", ""],
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "reddit"
    assert doc.authorship == "user_authored"
    assert doc.content == "Hello from chat!"
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2024
    assert doc.timestamp.month == 6


async def test_parse_chat_empty_message_skipped(parser: RedditExportParser, tmp_dir: Path):
    """Chat messages with empty message are skipped."""
    _write_csv(tmp_dir / "chat_history.csv", _CHAT_HEADERS, [
        ["msg1", "2024-06-15 10:30:00 UTC", "", "/u/user", "", "", "", "", "", ""],
        ["msg2", "2024-06-15 10:30:00 UTC", "", "/u/user", "   ", "", "", "", "", ""],
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 0


# ------------------------------------------------------------------
# Timestamp parsing
# ------------------------------------------------------------------


async def test_timestamp_utc_format(parser: RedditExportParser, tmp_dir: Path):
    """'2012-04-30 05:33:57 UTC' format is parsed."""
    _write_csv(tmp_dir / "posts.csv", _POST_HEADERS, [
        ["ts1", "", "2012-04-30 05:33:57 UTC", "", "test", "0", "ts test", "", "body"],
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is not None
    assert docs[0].timestamp.year == 2012
    assert docs[0].timestamp.month == 4
    assert docs[0].timestamp.day == 30


async def test_timestamp_missing(parser: RedditExportParser, tmp_dir: Path):
    """Missing date field results in None."""
    _write_csv(tmp_dir / "posts.csv", _POST_HEADERS, [
        ["ts2", "", "", "", "test", "0", "no timestamp", "", "body"],
    ])
    docs = await parser.parse(tmp_dir)
    assert docs[0].timestamp is None


# ------------------------------------------------------------------
# Multiple files combined
# ------------------------------------------------------------------


async def test_parse_multiple_files(parser: RedditExportParser, tmp_dir: Path):
    """Posts, comments, and chat from separate files are combined."""
    _write_csv(tmp_dir / "posts.csv", _POST_HEADERS, [
        ["p1", "/p1/", "2024-01-01 00:00:00 UTC", "", "test", "0", "Post 1", "", "Body 1"],
        ["p2", "/p2/", "2024-01-02 00:00:00 UTC", "", "test", "0", "Post 2", "", "Body 2"],
    ])
    _write_csv(tmp_dir / "comments.csv", _COMMENT_HEADERS, [
        ["c1", "/c1/", "2024-01-03 00:00:00 UTC", "", "test", "0", "", "", "Comment 1", ""],
    ])
    _write_csv(tmp_dir / "chat_history.csv", _CHAT_HEADERS, [
        ["m1", "2024-01-04 00:00:00 UTC", "", "/u/user", "Chat 1", "", "", "", "", ""],
    ])
    docs = await parser.parse(tmp_dir)

    assert len(docs) == 4
    sources = {d.source_ref for d in docs}
    assert "/p1/" in sources
    assert "/p2/" in sources
    assert "/c1/" in sources
    assert "m1" in sources


# ------------------------------------------------------------------
# Saved posts/comments are skipped (no content in real exports)
# ------------------------------------------------------------------


async def test_saved_posts_not_parsed(parser: RedditExportParser, tmp_dir: Path):
    """saved_posts.csv only has id/permalink -- parser does not read it."""
    # Write a saved_posts.csv with just id,permalink columns
    _write_csv(tmp_dir / "saved_posts.csv", ["id", "permalink"], [
        ["sp1", "https://reddit.com/r/other/comments/sp1/"],
    ])
    # No posts.csv or comments.csv -- should yield nothing
    docs = await parser.parse(tmp_dir)
    assert len(docs) == 0
