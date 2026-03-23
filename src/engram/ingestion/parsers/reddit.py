"""Reddit data export parser (JSON archive from 'Request Your Data')."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from engram.ingestion.parsers.base import RawDocument

# Files we look for in a Reddit data export
_POST_FILES = ("posts.json",)
_COMMENT_FILES = ("comments.json",)
_SAVED_POST_FILES = ("saved_posts.json",)
_SAVED_COMMENT_FILES = ("saved_comments.json",)
_ALL_KNOWN_FILES = _POST_FILES + _COMMENT_FILES + _SAVED_POST_FILES + _SAVED_COMMENT_FILES


class RedditExportParser:
    """Parse a Reddit data export directory containing JSON files."""

    def __init__(self, username: str = "") -> None:
        self.username = username

    def validate(self, export_path: Path) -> bool:
        """Check that the path is a directory containing Reddit export JSON files."""
        if not export_path.is_dir():
            return False
        for name in _ALL_KNOWN_FILES:
            if (export_path / name).is_file():
                return True
        return False

    async def parse(self, export_path: Path) -> list[RawDocument]:
        """Parse all recognised JSON files in the export directory."""
        documents: list[RawDocument] = []

        # Posts
        for name in _POST_FILES:
            path = export_path / name
            if path.is_file():
                documents.extend(self._parse_posts(path))

        # Comments
        for name in _COMMENT_FILES:
            path = export_path / name
            if path.is_file():
                documents.extend(self._parse_comments(path))

        # Saved posts (third-party content)
        for name in _SAVED_POST_FILES:
            path = export_path / name
            if path.is_file():
                documents.extend(self._parse_posts(path, authorship="received"))

        # Saved comments (third-party content)
        for name in _SAVED_COMMENT_FILES:
            path = export_path / name
            if path.is_file():
                documents.extend(self._parse_comments(path, authorship="received"))

        return documents

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_posts(
        self, path: Path, authorship: str = "user_authored"
    ) -> list[RawDocument]:
        data = self._load_json(path)
        if not isinstance(data, list):
            return []

        docs: list[RawDocument] = []
        for item in data:
            title = self._get_str(item, "title")
            body = self._get_str(item, "selftext") or self._get_str(item, "body")
            permalink = self._get_str(item, "permalink")
            timestamp = self._parse_timestamp(item)

            content = f"{title}\n\n{body}".strip() if title else (body or "").strip()
            if not content:
                continue

            docs.append(
                RawDocument(
                    content=content,
                    source="reddit",
                    source_ref=permalink or f"reddit-post-{hash(content)}",
                    timestamp=timestamp,
                    authorship=authorship,
                )
            )
        return docs

    def _parse_comments(
        self, path: Path, authorship: str = "user_authored"
    ) -> list[RawDocument]:
        data = self._load_json(path)
        if not isinstance(data, list):
            return []

        docs: list[RawDocument] = []
        for item in data:
            body = self._get_str(item, "body")
            permalink = self._get_str(item, "permalink")
            timestamp = self._parse_timestamp(item)

            content = (body or "").strip()
            if not content:
                continue

            docs.append(
                RawDocument(
                    content=content,
                    source="reddit",
                    source_ref=permalink or f"reddit-comment-{hash(content)}",
                    timestamp=timestamp,
                    authorship=authorship,
                )
            )
        return docs

    @staticmethod
    def _load_json(path: Path) -> list | dict | None:
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _get_str(obj: dict, key: str) -> str:
        """Safely get a string value from a dict."""
        val = obj.get(key)
        if val is None:
            return ""
        return str(val)

    @staticmethod
    def _parse_timestamp(item: dict) -> datetime | None:
        """Parse created_utc (unix timestamp) or created (ISO string)."""
        # Try unix timestamp first
        for key in ("created_utc", "created"):
            val = item.get(key)
            if val is None:
                continue
            # Numeric unix timestamp
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val, tz=UTC)
            # String that looks like a number
            if isinstance(val, str):
                try:
                    return datetime.fromtimestamp(float(val), tz=UTC)
                except ValueError:
                    pass
                # ISO format string
                try:
                    dt = datetime.fromisoformat(val)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    return dt
                except ValueError:
                    pass
        return None
