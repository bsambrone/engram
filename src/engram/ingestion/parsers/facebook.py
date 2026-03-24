"""Facebook data export parser (JSON format from 'Download Your Information')."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from engram.ingestion.parsers.base import RawDocument

# Top-level directory names we recognise in a Facebook export
_KNOWN_DIRS = (
    "posts",
    "messages",
    "comments_and_reactions",
    "your_facebook_activity",
)


class FacebookExportParser:
    """Parse a Facebook JSON data export directory."""

    def validate(self, export_path: Path) -> bool:
        """Check that the path looks like a Facebook export."""
        if not export_path.is_dir():
            return False
        # Direct child directories
        for name in _KNOWN_DIRS:
            if (export_path / name).is_dir():
                return True
        # Nested under your_facebook_activity/
        activity_dir = export_path / "your_facebook_activity"
        if activity_dir.is_dir():
            for name in ("posts", "messages", "comments_and_reactions"):
                if (activity_dir / name).is_dir():
                    return True
        return False

    async def parse(self, export_path: Path) -> list[RawDocument]:
        """Parse posts, comments, and messages from the export."""
        documents: list[RawDocument] = []

        # Resolve the activity root (may or may not have the wrapper dir)
        roots = [export_path]
        activity_dir = export_path / "your_facebook_activity"
        if activity_dir.is_dir():
            roots.append(activity_dir)

        for root in roots:
            documents.extend(self._parse_posts_dir(root / "posts"))
            documents.extend(self._parse_comments_dir(root / "comments_and_reactions"))
            documents.extend(self._parse_messages_dir(root / "messages"))

        return documents

    # ------------------------------------------------------------------
    # Posts
    # ------------------------------------------------------------------

    def _parse_posts_dir(self, posts_dir: Path) -> list[RawDocument]:
        if not posts_dir.is_dir():
            return []
        docs: list[RawDocument] = []
        for json_file in sorted(posts_dir.glob("*.json")):
            docs.extend(self._parse_posts_file(json_file))
        return docs

    def _parse_posts_file(self, path: Path) -> list[RawDocument]:
        data = _load_json(path)
        if not isinstance(data, list):
            return []

        docs: list[RawDocument] = []
        for item in data:
            # Facebook wraps post text in data -> [{ post }]
            text = _extract_post_text(item)
            if not text:
                continue
            timestamp = _parse_fb_timestamp(item)

            # Extract people from photo tags if present
            people = _extract_photo_tag_names(item)
            # Collect image URIs from attachments/media
            image_refs = _extract_media_uris(item)

            docs.append(
                RawDocument(
                    content=text,
                    source="facebook",
                    source_ref=f"facebook-post-{hash(text)}",
                    timestamp=timestamp,
                    authorship="user_authored",
                    people=people,
                    image_refs=image_refs,
                )
            )
        return docs

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def _parse_comments_dir(self, comments_dir: Path) -> list[RawDocument]:
        if not comments_dir.is_dir():
            return []
        docs: list[RawDocument] = []
        for json_file in sorted(comments_dir.glob("*.json")):
            docs.extend(self._parse_comments_file(json_file))
        return docs

    def _parse_comments_file(self, path: Path) -> list[RawDocument]:
        data = _load_json(path)
        if not isinstance(data, list):
            return []

        docs: list[RawDocument] = []
        for item in data:
            text = _extract_comment_text(item)
            if not text:
                continue
            timestamp = _parse_fb_timestamp(item)
            docs.append(
                RawDocument(
                    content=text,
                    source="facebook",
                    source_ref=f"facebook-comment-{hash(text)}",
                    timestamp=timestamp,
                    authorship="user_authored",
                )
            )
        return docs

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def _parse_messages_dir(self, messages_dir: Path) -> list[RawDocument]:
        if not messages_dir.is_dir():
            return []
        docs: list[RawDocument] = []
        inbox_dir = messages_dir / "inbox"
        if not inbox_dir.is_dir():
            return []
        for convo_dir in sorted(inbox_dir.iterdir()):
            if convo_dir.is_dir():
                for json_file in sorted(convo_dir.glob("*.json")):
                    docs.extend(self._parse_message_file(json_file))
        return docs

    def _parse_message_file(self, path: Path) -> list[RawDocument]:
        data = _load_json(path)
        if not isinstance(data, dict):
            return []

        messages = data.get("messages", [])
        if not isinstance(messages, list):
            return []

        docs: list[RawDocument] = []
        for msg in messages:
            content = _fix_encoding(msg.get("content", ""))
            if not content.strip():
                continue
            sender = _fix_encoding(msg.get("sender_name", ""))
            timestamp = _parse_fb_timestamp(msg)
            # Messages have a sender; we treat all as received (from others)
            # since we cannot reliably determine the export owner's name.
            docs.append(
                RawDocument(
                    content=content,
                    source="facebook",
                    source_ref=f"facebook-message-{hash(content + sender)}",
                    timestamp=timestamp,
                    authorship="received",
                )
            )
        return docs


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _fix_encoding(text: str) -> str:
    """Fix Facebook's UTF-8-as-latin-1 encoding quirk."""
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def _load_json(path: Path) -> list | dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _extract_post_text(item: dict) -> str:
    """Extract post text from various Facebook export formats."""
    # Format 1: { "data": [{ "post": "text" }] }
    data_list = item.get("data", [])
    if isinstance(data_list, list):
        for entry in data_list:
            if isinstance(entry, dict):
                post_text = entry.get("post", "")
                if post_text:
                    return _fix_encoding(str(post_text)).strip()

    # Format 2: direct "post" key
    post_text = item.get("post", "")
    if post_text:
        return _fix_encoding(str(post_text)).strip()

    # Format 3: direct "text" key
    text = item.get("text", "")
    if text:
        return _fix_encoding(str(text)).strip()

    return ""


def _extract_comment_text(item: dict) -> str:
    """Extract comment text from Facebook export formats."""
    # Format: { "data": [{ "comment": { "comment": "text" } }] }
    data_list = item.get("data", [])
    if isinstance(data_list, list):
        for entry in data_list:
            if isinstance(entry, dict):
                comment_obj = entry.get("comment", {})
                if isinstance(comment_obj, dict):
                    text = comment_obj.get("comment", "")
                    if text:
                        return _fix_encoding(str(text)).strip()
                # Simpler format: { "comment": "text" }
                if isinstance(comment_obj, str) and comment_obj:
                    return _fix_encoding(comment_obj).strip()

    # Direct comment key
    comment = item.get("comment", "")
    if isinstance(comment, str) and comment:
        return _fix_encoding(comment).strip()

    return ""


def _extract_photo_tag_names(item: dict) -> list[str]:
    """Extract people names from Facebook photo tags.

    Facebook exports include tagged photos with a structure like:
    {"tags": [{"name": "John Smith"}, {"name": "Sarah Connor"}]}

    Tags may also appear nested under media or attachments.
    """
    names: list[str] = []
    seen: set[str] = set()

    def _collect_tags(obj: dict) -> None:
        tags = obj.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, dict):
                    name = _fix_encoding(str(tag.get("name", "") or "")).strip()
                    if name and name not in seen:
                        seen.add(name)
                        names.append(name)

    # Check top-level tags
    _collect_tags(item)

    # Check tags within media_metadata or attachments
    for attach_list in (item.get("attachments", []), item.get("media", [])):
        if isinstance(attach_list, list):
            for attachment in attach_list:
                if isinstance(attachment, dict):
                    _collect_tags(attachment)
                    # Also check nested data within attachments
                    for nested in attachment.get("data", []):
                        if isinstance(nested, dict):
                            _collect_tags(nested)
                            media = nested.get("media", {})
                            if isinstance(media, dict):
                                _collect_tags(media)

    return names


def _extract_media_uris(item: dict) -> list[str]:
    """Extract media file URIs from a Facebook post item."""
    uris: list[str] = []

    # Check direct uri
    uri = item.get("uri")
    if uri:
        uris.append(str(uri))

    # Check attachments and media lists
    for attach_list in (item.get("attachments", []), item.get("media", [])):
        if isinstance(attach_list, list):
            for attachment in attach_list:
                if isinstance(attachment, dict):
                    uri = attachment.get("uri")
                    if uri:
                        uris.append(str(uri))
                    for nested in attachment.get("data", []):
                        if isinstance(nested, dict):
                            media = nested.get("media", {})
                            if isinstance(media, dict):
                                uri = media.get("uri")
                                if uri:
                                    uris.append(str(uri))

    return uris


def _parse_fb_timestamp(item: dict) -> datetime | None:
    """Parse Facebook's timestamp (unix seconds)."""
    ts = item.get("timestamp")
    if ts is None:
        ts = item.get("timestamp_ms")
        if ts is not None:
            # Convert milliseconds to seconds
            try:
                return datetime.fromtimestamp(int(ts) / 1000, tz=UTC)
            except (ValueError, OSError):
                return None
    if ts is not None:
        try:
            return datetime.fromtimestamp(int(ts), tz=UTC)
        except (ValueError, OSError):
            return None
    return None
