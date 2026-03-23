"""Gmail MBOX export parser for Google Takeout."""

from __future__ import annotations

import mailbox
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from engram.ingestion.parsers.base import RawDocument


class GmailExportParser:
    """Parse Google Takeout Gmail MBOX export."""

    def __init__(self, user_email: str = "") -> None:
        self.user_email = user_email.lower()

    def validate(self, export_path: Path) -> bool:
        """Check that the path contains .mbox files."""
        if export_path.is_file() and export_path.suffix == ".mbox":
            return True
        if export_path.is_dir():
            return any(export_path.glob("**/*.mbox"))
        return False

    async def parse(self, export_path: Path) -> list[RawDocument]:
        """Parse MBOX file(s) into RawDocuments."""
        documents: list[RawDocument] = []
        mbox_files: list[Path] = []

        if export_path.is_file():
            mbox_files = [export_path]
        elif export_path.is_dir():
            mbox_files = list(export_path.glob("**/*.mbox"))

        for mbox_path in mbox_files:
            mbox = mailbox.mbox(str(mbox_path))
            for msg in mbox:
                doc = self._parse_message(msg)
                if doc:
                    documents.append(doc)

        return documents

    def _parse_message(self, msg: mailbox.mboxMessage) -> RawDocument | None:
        """Parse a single email message into a RawDocument."""
        from_addr = msg.get("From", "").lower()
        subject = msg.get("Subject", "")
        date_str = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")

        # Parse timestamp
        try:
            timestamp = parsedate_to_datetime(date_str)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
        except Exception:
            timestamp = None

        # Determine authorship
        is_sent = bool(self.user_email) and self.user_email in from_addr
        authorship = "user_authored" if is_sent else "received"

        # Extract body text
        body = self._extract_body(msg)
        if not body or not body.strip():
            return None

        # Prepend subject for context
        content = f"Subject: {subject}\n\n{body}" if subject else body

        # Extract images
        images = self._extract_images(msg)

        return RawDocument(
            content=content,
            source="gmail",
            source_ref=message_id or f"gmail-{hash(content)}",
            timestamp=timestamp,
            authorship=authorship,
            images=images,
        )

    def _extract_body(self, msg: mailbox.mboxMessage) -> str:
        """Extract plain text body from email message."""
        if msg.is_multipart():
            # Try plain text first
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
            # Fallback to HTML if no plain text
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""

    def _extract_images(self, msg: mailbox.mboxMessage) -> list[bytes]:
        """Extract image attachments from a message."""
        images: list[bytes] = []
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type().startswith("image/"):
                    payload = part.get_payload(decode=True)
                    if payload:
                        images.append(payload)
        return images
