"""Tests for the Gmail MBOX export parser."""

import mailbox
import tempfile
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pytest

from engram.ingestion.parsers.base import ExportParser
from engram.ingestion.parsers.gmail import GmailExportParser


def _create_test_mbox(messages: list[dict]) -> Path:
    """Create a temporary MBOX file with test messages."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mbox", delete=False)
    tmp.close()
    mbox = mailbox.mbox(tmp.name)
    for msg_data in messages:
        msg = MIMEText(msg_data["body"])
        msg["From"] = msg_data.get("from", "other@example.com")
        msg["Subject"] = msg_data.get("subject", "Test")
        msg["Date"] = msg_data.get("date", "Mon, 1 Jan 2025 12:00:00 +0000")
        msg["Message-ID"] = msg_data.get(
            "id", f"<test-{hash(msg_data['body'])}@example.com>"
        )
        mbox.add(msg)
    mbox.close()
    return Path(tmp.name)


@pytest.fixture
def parser() -> GmailExportParser:
    return GmailExportParser(user_email="me@example.com")


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


async def test_gmail_parser_implements_protocol():
    """GmailExportParser satisfies the ExportParser protocol."""
    assert isinstance(GmailExportParser(), ExportParser)


async def test_validate_mbox_file(parser: GmailExportParser, tmp_dir: Path):
    """validate returns True for a .mbox file."""
    mbox_path = _create_test_mbox([{"body": "Hello"}])
    assert parser.validate(mbox_path) is True


async def test_validate_mbox_directory(parser: GmailExportParser, tmp_dir: Path):
    """validate returns True for a directory containing .mbox files."""
    mbox_path = _create_test_mbox([{"body": "Hello"}])
    dest = tmp_dir / "Mail" / "All mail.mbox"
    dest.parent.mkdir(parents=True, exist_ok=True)
    mbox_path.rename(dest)
    assert parser.validate(tmp_dir) is True


async def test_validate_non_mbox(parser: GmailExportParser, tmp_dir: Path):
    """validate returns False for paths without .mbox files."""
    txt = tmp_dir / "notes.txt"
    txt.write_text("not mbox")
    assert parser.validate(txt) is False
    assert parser.validate(tmp_dir / "nonexistent") is False


async def test_validate_empty_directory(parser: GmailExportParser, tmp_dir: Path):
    """validate returns False for an empty directory."""
    assert parser.validate(tmp_dir) is False


async def test_parse_single_message(parser: GmailExportParser):
    """Parsing an mbox with one message returns one RawDocument."""
    mbox_path = _create_test_mbox([
        {
            "body": "Hello, world!",
            "from": "other@example.com",
            "subject": "Greetings",
            "date": "Tue, 14 Jan 2025 09:30:00 +0000",
            "id": "<msg-001@example.com>",
        }
    ])

    docs = await parser.parse(mbox_path)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "gmail"
    assert doc.source_ref == "<msg-001@example.com>"
    assert "Hello, world!" in doc.content
    assert doc.timestamp is not None
    assert doc.timestamp.year == 2025
    assert doc.timestamp.month == 1
    assert doc.timestamp.day == 14


async def test_parse_authorship_sent_vs_received(parser: GmailExportParser):
    """Messages from user_email are 'user_authored'; others are 'received'."""
    mbox_path = _create_test_mbox([
        {
            "body": "Sent by me",
            "from": "me@example.com",
            "subject": "Outgoing",
            "id": "<sent@example.com>",
        },
        {
            "body": "Sent by someone else",
            "from": "friend@example.com",
            "subject": "Incoming",
            "id": "<received@example.com>",
        },
    ])

    docs = await parser.parse(mbox_path)

    assert len(docs) == 2
    sent = next(d for d in docs if d.source_ref == "<sent@example.com>")
    received = next(d for d in docs if d.source_ref == "<received@example.com>")
    assert sent.authorship == "user_authored"
    assert received.authorship == "received"


async def test_parse_empty_body_skipped():
    """Messages with empty bodies are skipped."""
    parser = GmailExportParser()
    mbox_path = _create_test_mbox([
        {"body": "", "subject": "Empty"},
        {"body": "Has content", "subject": "Full"},
    ])

    docs = await parser.parse(mbox_path)

    # Only the non-empty message should be returned
    assert len(docs) == 1
    assert "Has content" in docs[0].content


async def test_parse_multiple_messages(parser: GmailExportParser):
    """Parsing an mbox with multiple messages returns all of them."""
    messages = [
        {"body": f"Message {i}", "id": f"<msg-{i}@example.com>"}
        for i in range(5)
    ]
    mbox_path = _create_test_mbox(messages)

    docs = await parser.parse(mbox_path)

    assert len(docs) == 5
    refs = {d.source_ref for d in docs}
    for i in range(5):
        assert f"<msg-{i}@example.com>" in refs


async def test_subject_prepended_to_content(parser: GmailExportParser):
    """Subject line is prepended to the content."""
    mbox_path = _create_test_mbox([
        {"body": "Body text here", "subject": "Important Topic"},
    ])

    docs = await parser.parse(mbox_path)

    assert len(docs) == 1
    assert docs[0].content.startswith("Subject: Important Topic\n\n")
    assert "Body text here" in docs[0].content


async def test_parse_directory_of_mbox_files(parser: GmailExportParser, tmp_dir: Path):
    """Parsing a directory collects messages from all .mbox files within it."""
    mail_dir = tmp_dir / "Takeout" / "Mail"
    mail_dir.mkdir(parents=True)

    mbox1 = _create_test_mbox([{"body": "From inbox", "id": "<inbox@example.com>"}])
    mbox2 = _create_test_mbox([{"body": "From sent", "id": "<sent@example.com>"}])

    mbox1.rename(mail_dir / "Inbox.mbox")
    mbox2.rename(mail_dir / "Sent.mbox")

    docs = await parser.parse(tmp_dir)

    assert len(docs) == 2
    refs = {d.source_ref for d in docs}
    assert "<inbox@example.com>" in refs
    assert "<sent@example.com>" in refs


async def test_parse_multipart_with_image():
    """Multipart messages with image attachments extract images."""
    parser = GmailExportParser()

    # Build a multipart message with text and an image
    tmp = tempfile.NamedTemporaryFile(suffix=".mbox", delete=False)
    tmp.close()
    mbox = mailbox.mbox(tmp.name)

    msg = MIMEMultipart()
    msg["From"] = "sender@example.com"
    msg["Subject"] = "Photo attached"
    msg["Date"] = "Wed, 15 Jan 2025 10:00:00 +0000"
    msg["Message-ID"] = "<photo@example.com>"
    msg.attach(MIMEText("See attached photo."))
    # Create a small fake PNG image (just bytes, not a real image)
    fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    img_part = MIMEImage(fake_image, _subtype="png")
    msg.attach(img_part)
    mbox.add(msg)
    mbox.close()

    docs = await parser.parse(Path(tmp.name))

    assert len(docs) == 1
    assert docs[0].images
    assert len(docs[0].images) == 1
    assert docs[0].images[0] == fake_image


async def test_no_user_email_defaults_received():
    """When user_email is not set, all messages default to 'received'."""
    parser = GmailExportParser()  # no user_email
    mbox_path = _create_test_mbox([
        {"body": "Some content", "from": "anyone@example.com"},
    ])

    docs = await parser.parse(mbox_path)

    assert len(docs) == 1
    assert docs[0].authorship == "received"
