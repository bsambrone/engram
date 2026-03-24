"""Base protocol and data structures for export parsers."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class RawDocument:
    """A single parsed document from an export source."""

    content: str
    source: str  # "file", "gmail", "reddit", "facebook", "instagram"
    source_ref: str  # filename, message ID, permalink
    timestamp: datetime | None = None
    authorship: str = "user_authored"
    images: list[bytes] = field(default_factory=list)
    image_refs: list[str] = field(default_factory=list)  # paths to associated images
    people: list[str] = field(default_factory=list)  # people extracted at parse time


@runtime_checkable
class ExportParser(Protocol):
    """Protocol that all export parsers must implement."""

    def validate(self, export_path: Path) -> bool:
        """Check whether the export path is valid for this parser."""
        ...

    async def parse(self, export_path: Path) -> list[RawDocument]:
        """Parse the export at the given path and return raw documents."""
        ...
