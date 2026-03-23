"""Tests for the FileParser."""

import json
import tempfile
from pathlib import Path

import pytest

from engram.ingestion.parsers.base import ExportParser, RawDocument
from engram.ingestion.parsers.file import FileParser


@pytest.fixture
def parser() -> FileParser:
    return FileParser()


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


async def test_parse_txt_file(parser: FileParser, tmp_dir: Path):
    """Parsing a .txt file returns a single RawDocument with correct content."""
    txt_file = tmp_dir / "note.txt"
    txt_file.write_text("Hello, world!", encoding="utf-8")

    docs = await parser.parse(txt_file)

    assert len(docs) == 1
    assert docs[0].content == "Hello, world!"
    assert docs[0].source == "file"
    assert docs[0].source_ref == "note.txt"
    assert docs[0].authorship == "user_authored"
    assert docs[0].timestamp is not None


async def test_parse_md_file(parser: FileParser, tmp_dir: Path):
    """Parsing a .md file returns a single RawDocument."""
    md_file = tmp_dir / "readme.md"
    md_file.write_text("# Title\n\nSome markdown content.", encoding="utf-8")

    docs = await parser.parse(md_file)

    assert len(docs) == 1
    assert docs[0].content == "# Title\n\nSome markdown content."
    assert docs[0].source == "file"
    assert docs[0].source_ref == "readme.md"


async def test_parse_json_file(parser: FileParser, tmp_dir: Path):
    """Parsing a .json file with a list produces one doc per item."""
    json_file = tmp_dir / "data.json"
    data = [{"text": "first"}, {"text": "second"}]
    json_file.write_text(json.dumps(data), encoding="utf-8")

    docs = await parser.parse(json_file)

    assert len(docs) == 2
    assert docs[0].source_ref == "data.json[0]"
    assert docs[1].source_ref == "data.json[1]"
    # Each doc content should be the JSON-serialized item
    assert json.loads(docs[0].content) == {"text": "first"}
    assert json.loads(docs[1].content) == {"text": "second"}


async def test_parse_json_single_object(parser: FileParser, tmp_dir: Path):
    """Parsing a .json file with a single object produces one doc."""
    json_file = tmp_dir / "single.json"
    data = {"key": "value"}
    json_file.write_text(json.dumps(data), encoding="utf-8")

    docs = await parser.parse(json_file)

    assert len(docs) == 1
    assert docs[0].source_ref == "single.json"
    assert json.loads(docs[0].content) == {"key": "value"}


async def test_parse_directory(parser: FileParser, tmp_dir: Path):
    """Parsing a directory collects all supported files."""
    (tmp_dir / "a.txt").write_text("Text file", encoding="utf-8")
    (tmp_dir / "b.md").write_text("Markdown file", encoding="utf-8")
    (tmp_dir / "c.json").write_text(json.dumps({"x": 1}), encoding="utf-8")
    (tmp_dir / "d.pdf").write_bytes(b"not supported")  # should be skipped

    docs = await parser.parse(tmp_dir)

    # 3 files: a.txt, b.md, c.json (d.pdf is skipped)
    assert len(docs) == 3
    refs = {d.source_ref for d in docs}
    assert "a.txt" in refs
    assert "b.md" in refs
    assert "c.json" in refs


async def test_validate_file(parser: FileParser, tmp_dir: Path):
    """validate returns True for supported files, False otherwise."""
    txt_file = tmp_dir / "test.txt"
    txt_file.write_text("content", encoding="utf-8")
    assert parser.validate(txt_file) is True

    pdf_file = tmp_dir / "test.pdf"
    pdf_file.write_bytes(b"content")
    assert parser.validate(pdf_file) is False


async def test_validate_directory(parser: FileParser, tmp_dir: Path):
    """validate returns True for dirs containing supported files."""
    (tmp_dir / "file.md").write_text("md content", encoding="utf-8")
    assert parser.validate(tmp_dir) is True


async def test_validate_empty_directory(parser: FileParser, tmp_dir: Path):
    """validate returns False for empty directories."""
    empty = tmp_dir / "empty"
    empty.mkdir()
    assert parser.validate(empty) is False


async def test_file_parser_implements_protocol():
    """FileParser satisfies the ExportParser protocol."""
    assert isinstance(FileParser(), ExportParser)


async def test_raw_document_defaults():
    """RawDocument dataclass has correct default values."""
    doc = RawDocument(content="test", source="file", source_ref="test.txt")
    assert doc.timestamp is None
    assert doc.authorship == "user_authored"
    assert doc.images == []
