"""Instagram data export parser (JSON format from 'Download Your Data')."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from engram.ingestion.parsers.base import RawDocument

# Top-level directory names we recognise in an Instagram export
_KNOWN_DIRS = (
    "content",
    "messages",
    "your_instagram_activity",
)


class InstagramExportParser:
    """Parse an Instagram JSON data export directory."""

    def validate(self, export_path: Path) -> bool:
        """Check that the path looks like an Instagram export."""
        if not export_path.is_dir():
            return False
        # Direct child directories
        for name in _KNOWN_DIRS:
            if (export_path / name).is_dir():
                return True
        # Nested under your_instagram_activity/
        activity_dir = export_path / "your_instagram_activity"
        if activity_dir.is_dir():
            for name in ("content", "messages"):
                if (activity_dir / name).is_dir():
                    return True
        return False

    async def parse(self, export_path: Path) -> list[RawDocument]:
        """Parse posts, stories, and messages from the export."""
        documents: list[RawDocument] = []

        # Resolve the activity root (may or may not have the wrapper dir)
        roots = [export_path]
        activity_dir = export_path / "your_instagram_activity"
        if activity_dir.is_dir():
            roots.append(activity_dir)

        for root in roots:
            documents.extend(self._parse_content_dir(root / "content"))
            documents.extend(self._parse_messages_dir(root / "messages"))

        return documents

    # ------------------------------------------------------------------
    # Content (posts, stories)
    # ------------------------------------------------------------------

    def _parse_content_dir(self, content_dir: Path) -> list[RawDocument]:
        if not content_dir.is_dir():
            return []
        docs: list[RawDocument] = []
        for json_file in sorted(content_dir.glob("*.json")):
            docs.extend(self._parse_content_file(json_file))
        return docs

    def _parse_content_file(self, path: Path) -> list[RawDocument]:
        data = _load_json(path)
        if not isinstance(data, list):
            return []

        docs: list[RawDocument] = []
        for item in data:
            text = _extract_content_text(item)
            if not text:
                continue
            timestamp = _parse_ig_timestamp(item)
            docs.append(
                RawDocument(
                    content=text,
                    source="instagram",
                    source_ref=f"instagram-content-{hash(text)}",
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
            timestamp = _parse_ig_timestamp(msg)
            docs.append(
                RawDocument(
                    content=content,
                    source="instagram",
                    source_ref=f"instagram-message-{hash(content + sender)}",
                    timestamp=timestamp,
                    authorship="received",
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


def _extract_content_text(item: dict) -> str:
    """Extract text from an Instagram content item (post or story)."""
    # Format: { "media": [{ ... }], "title": "caption text" }
    title = item.get("title", "")
    if title:
        return _fix_encoding(str(title)).strip()

    # Alternative: "caption" key
    caption = item.get("caption", "")
    if caption:
        return _fix_encoding(str(caption)).strip()

    # Alternative: "text" key
    text = item.get("text", "")
    if text:
        return _fix_encoding(str(text)).strip()

    return ""


def _parse_ig_timestamp(item: dict) -> datetime | None:
    """Parse Instagram's timestamp (unix seconds or ISO string)."""
    # Try creation_timestamp (unix seconds)
    ts = item.get("creation_timestamp")
    if ts is None:
        ts = item.get("timestamp")
    if ts is None:
        ts = item.get("timestamp_ms")
        if ts is not None:
            try:
                return datetime.fromtimestamp(int(ts) / 1000, tz=UTC)
            except (ValueError, OSError):
                return None

    if ts is not None:
        if isinstance(ts, (int, float)):
            try:
                return datetime.fromtimestamp(ts, tz=UTC)
            except (ValueError, OSError):
                return None
        if isinstance(ts, str):
            try:
                return datetime.fromtimestamp(float(ts), tz=UTC)
            except ValueError:
                pass
            try:
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except ValueError:
                pass
    return None
