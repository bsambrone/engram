"""Reddit data export parser (CSV archive from 'Request Your Data')."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from engram.ingestion.parsers.base import RawDocument


class RedditExportParser:
    """Parse a Reddit data export directory containing CSV files."""

    def validate(self, export_path: Path) -> bool:
        """Check that the path is a directory containing Reddit export CSV files."""
        if not export_path.is_dir():
            return False
        return (export_path / "posts.csv").exists() or (
            export_path / "comments.csv"
        ).exists()

    async def parse(self, export_path: Path) -> list[RawDocument]:
        """Parse posts, comments, and chat history from the export directory."""
        docs: list[RawDocument] = []
        docs.extend(self._parse_posts(export_path / "posts.csv"))
        docs.extend(self._parse_comments(export_path / "comments.csv"))
        docs.extend(self._parse_chat(export_path / "chat_history.csv"))
        return docs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_posts(self, path: Path) -> list[RawDocument]:
        if not path.exists():
            return []
        docs: list[RawDocument] = []
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                body = row.get("body", "").strip()
                title = row.get("title", "").strip()
                if not body and not title:
                    continue
                content = f"{title}\n\n{body}" if body else title
                docs.append(
                    RawDocument(
                        content=content,
                        source="reddit",
                        source_ref=row.get("permalink", ""),
                        timestamp=self._parse_date(row.get("date", "")),
                        authorship="user_authored",
                    )
                )
        return docs

    def _parse_comments(self, path: Path) -> list[RawDocument]:
        if not path.exists():
            return []
        docs: list[RawDocument] = []
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                body = row.get("body", "").strip()
                if not body:
                    continue
                docs.append(
                    RawDocument(
                        content=body,
                        source="reddit",
                        source_ref=row.get("permalink", ""),
                        timestamp=self._parse_date(row.get("date", "")),
                        authorship="user_authored",
                    )
                )
        return docs

    def _parse_chat(self, path: Path) -> list[RawDocument]:
        if not path.exists():
            return []
        docs: list[RawDocument] = []
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                message = row.get("message", "").strip()
                if not message:
                    continue
                docs.append(
                    RawDocument(
                        content=message,
                        source="reddit",
                        source_ref=row.get("message_id", ""),
                        timestamp=self._parse_date(row.get("created_at", "")),
                        authorship="user_authored",
                    )
                )
        return docs

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        """Parse ``'2012-04-30 05:33:57 UTC'`` format."""
        if not date_str or not date_str.strip():
            return None
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S %Z").replace(
                tzinfo=None,
            )
        except (ValueError, AttributeError):
            return None
