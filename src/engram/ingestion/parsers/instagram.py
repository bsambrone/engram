"""Instagram data export parser (JSON format from 'Download Your Data')."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from engram.ingestion.parsers.base import RawDocument

# The user's display name as it appears in message sender_name fields.
_USER_DISPLAY_NAME = "Bill Sambrone"


class InstagramExportParser:
    """Parse an Instagram JSON data export directory."""

    def __init__(self, user_display_name: str = _USER_DISPLAY_NAME) -> None:
        self.user_display_name = user_display_name

    def validate(self, export_path: Path) -> bool:
        """Check that the path looks like an Instagram export."""
        if not export_path.is_dir():
            return False
        activity_dir = export_path / "your_instagram_activity"
        if activity_dir.is_dir():
            # Check for media/, comments/, or messages/ under activity dir
            for name in ("media", "comments", "messages"):
                if (activity_dir / name).is_dir():
                    return True
        return False

    async def parse(self, export_path: Path) -> list[RawDocument]:
        """Parse posts, comments, and messages from the export."""
        documents: list[RawDocument] = []
        activity_dir = export_path / "your_instagram_activity"

        # Posts: your_instagram_activity/media/posts_1.json, posts_2.json, etc.
        documents.extend(self._parse_posts_dir(activity_dir / "media"))

        # Comments: your_instagram_activity/comments/post_comments_1.json, etc.
        documents.extend(self._parse_comments_dir(activity_dir / "comments"))

        # Messages: your_instagram_activity/messages/inbox/*/message_1.json
        documents.extend(self._parse_messages_dir(activity_dir / "messages"))

        return documents

    # ------------------------------------------------------------------
    # Posts  (your_instagram_activity/media/posts_*.json)
    # ------------------------------------------------------------------

    def _parse_posts_dir(self, media_dir: Path) -> list[RawDocument]:
        if not media_dir.is_dir():
            return []
        docs: list[RawDocument] = []
        for json_file in sorted(media_dir.glob("posts_*.json")):
            docs.extend(self._parse_posts_file(json_file))
        return docs

    def _parse_posts_file(self, path: Path) -> list[RawDocument]:
        data = _load_json(path)
        if not isinstance(data, list):
            return []

        docs: list[RawDocument] = []
        for item in data:
            # Posts wrap content in media[0].title and media[0].creation_timestamp
            media_list = item.get("media", [])
            if not media_list:
                continue
            first_media = media_list[0] if isinstance(media_list, list) and media_list else {}
            title = _fix_encoding(str(first_media.get("title", "") or "")).strip()
            if not title:
                continue
            timestamp = _parse_creation_timestamp(first_media)
            # Collect URIs for all media items associated with this post
            image_refs = [
                m.get("uri", "")
                for m in (media_list if isinstance(media_list, list) else [])
                if m.get("uri")
            ]
            docs.append(
                RawDocument(
                    content=title,
                    source="instagram",
                    source_ref=first_media.get("uri", f"instagram-post-{hash(title)}"),
                    timestamp=timestamp,
                    authorship="user_authored",
                    image_refs=image_refs,
                )
            )
        return docs

    # ------------------------------------------------------------------
    # Comments  (your_instagram_activity/comments/post_comments_*.json)
    # ------------------------------------------------------------------

    def _parse_comments_dir(self, comments_dir: Path) -> list[RawDocument]:
        if not comments_dir.is_dir():
            return []
        docs: list[RawDocument] = []
        for json_file in sorted(comments_dir.glob("post_comments_*.json")):
            docs.extend(self._parse_comments_file(json_file))
        return docs

    def _parse_comments_file(self, path: Path) -> list[RawDocument]:
        data = _load_json(path)
        if not isinstance(data, list):
            return []

        docs: list[RawDocument] = []
        for item in data:
            smd = item.get("string_map_data", {})
            comment_entry = smd.get("Comment", {})
            text = _fix_encoding(str(comment_entry.get("value", "") or "")).strip()
            if not text:
                continue
            time_entry = smd.get("Time", {})
            timestamp = _parse_unix_timestamp(time_entry.get("timestamp"))
            docs.append(
                RawDocument(
                    content=text,
                    source="instagram",
                    source_ref=f"instagram-comment-{hash(text)}",
                    timestamp=timestamp,
                    authorship="user_authored",
                )
            )
        return docs

    # ------------------------------------------------------------------
    # Messages  (your_instagram_activity/messages/inbox/*/message_*.json)
    # ------------------------------------------------------------------

    def _parse_messages_dir(self, messages_dir: Path) -> list[RawDocument]:
        if not messages_dir.is_dir():
            return []
        docs: list[RawDocument] = []
        # Scan both inbox and message_requests
        for subfolder in ("inbox", "message_requests"):
            folder = messages_dir / subfolder
            if not folder.is_dir():
                continue
            for convo_dir in sorted(folder.iterdir()):
                if convo_dir.is_dir():
                    for json_file in sorted(convo_dir.glob("message_*.json")):
                        docs.extend(self._parse_message_file(json_file))
        return docs

    def _parse_message_file(self, path: Path) -> list[RawDocument]:
        data = _load_json(path)
        if not isinstance(data, dict):
            return []

        messages = data.get("messages", [])
        if not isinstance(messages, list):
            return []

        # Collect unique conversation partners (non-user participants)
        participants = data.get("participants", [])
        conversation_partners: list[str] = []
        if isinstance(participants, list):
            for p in participants:
                name = _fix_encoding(str(p.get("name", "") or "")).strip()
                if name and name != self.user_display_name:
                    conversation_partners.append(name)

        docs: list[RawDocument] = []
        for msg in messages:
            content = _fix_encoding(str(msg.get("content", "") or ""))
            if not content.strip():
                continue
            sender = _fix_encoding(str(msg.get("sender_name", "") or ""))
            ts_ms = msg.get("timestamp_ms")
            timestamp = _parse_ms_timestamp(ts_ms)
            is_user = sender == self.user_display_name
            # Include sender name in source_ref for context
            source_ref = f"instagram-message-from-{sender}-{hash(content + sender)}"
            # Attach the sender as a person (for received messages)
            people = [sender] if (sender and not is_user) else []
            docs.append(
                RawDocument(
                    content=content,
                    source="instagram",
                    source_ref=source_ref,
                    timestamp=timestamp,
                    authorship="user_authored" if is_user else "received",
                    people=people,
                )
            )
        return docs


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _fix_encoding(text: str) -> str:
    """Fix Instagram's UTF-8-as-latin-1 encoding quirk (same as Facebook)."""
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


def _parse_creation_timestamp(item: dict) -> datetime | None:
    """Parse ``creation_timestamp`` (unix seconds) from a media dict."""
    return _parse_unix_timestamp(item.get("creation_timestamp"))


def _parse_unix_timestamp(val: int | float | str | None) -> datetime | None:
    """Convert a unix-seconds value to a datetime."""
    if val is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(val))
    except (ValueError, OSError, TypeError):
        return None


def _parse_ms_timestamp(val: int | float | str | None) -> datetime | None:
    """Convert a unix-milliseconds value to a naive UTC datetime."""
    if val is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(val) / 1000)
    except (ValueError, OSError, TypeError):
        return None
