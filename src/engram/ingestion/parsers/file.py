"""File parser for txt, md, and json files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from engram.ingestion.parsers.base import RawDocument

SUPPORTED_EXTENSIONS = {".txt", ".md", ".json"}


class FileParser:
    """Parses plain text, markdown, and JSON files from a directory or single file."""

    def validate(self, export_path: Path) -> bool:
        """Check that the path exists and contains supported files."""
        if export_path.is_file():
            return export_path.suffix.lower() in SUPPORTED_EXTENSIONS
        if export_path.is_dir():
            return any(
                f.suffix.lower() in SUPPORTED_EXTENSIONS
                for f in export_path.iterdir()
                if f.is_file()
            )
        return False

    async def parse(self, export_path: Path) -> list[RawDocument]:
        """Parse files at the given path into RawDocument instances."""
        if export_path.is_file():
            return self._parse_single(export_path)
        if export_path.is_dir():
            return self._parse_directory(export_path)
        return []

    def _parse_directory(self, directory: Path) -> list[RawDocument]:
        """Parse all supported files in a directory (non-recursive)."""
        docs: list[RawDocument] = []
        for filepath in sorted(directory.iterdir()):
            if filepath.is_file() and filepath.suffix.lower() in SUPPORTED_EXTENSIONS:
                docs.extend(self._parse_single(filepath))
        return docs

    def _parse_single(self, filepath: Path) -> list[RawDocument]:
        """Parse a single file into one or more RawDocument instances."""
        suffix = filepath.suffix.lower()
        text = filepath.read_text(encoding="utf-8")

        if suffix == ".json":
            return self._parse_json(filepath, text)

        # .txt and .md are treated the same
        stat = filepath.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        return [
            RawDocument(
                content=text,
                source="file",
                source_ref=filepath.name,
                timestamp=mtime,
                authorship="user_authored",
            )
        ]

    def _parse_json(self, filepath: Path, text: str) -> list[RawDocument]:
        """Parse a JSON file. If the top-level is a list, each item becomes a doc."""
        data = json.loads(text)
        stat = filepath.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        if isinstance(data, list):
            docs: list[RawDocument] = []
            for i, item in enumerate(data):
                content = json.dumps(item, ensure_ascii=False, indent=2) if not isinstance(
                    item, str
                ) else item
                docs.append(
                    RawDocument(
                        content=content,
                        source="file",
                        source_ref=f"{filepath.name}[{i}]",
                        timestamp=mtime,
                        authorship="user_authored",
                    )
                )
            return docs

        # Single object or scalar
        content = json.dumps(data, ensure_ascii=False, indent=2) if not isinstance(
            data, str
        ) else data
        return [
            RawDocument(
                content=content,
                source="file",
                source_ref=filepath.name,
                timestamp=mtime,
                authorship="user_authored",
            )
        ]
