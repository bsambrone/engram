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
        from_addr = str(msg.get("From") or "").lower()
        subject = str(msg.get("Subject") or "")
        date_str = str(msg.get("Date") or "")
        message_id = str(msg.get("Message-ID") or "")

        # Parse timestamp
        try:
            timestamp = parsedate_to_datetime(str(date_str))
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

    @staticmethod
    def _safe_decode(payload: bytes, charset: str | None) -> str:
        """Decode payload with fallback for malformed charset values."""
        if charset:
            # Strip any garbage from charset string
            charset = charset.strip().split()[0]
        try:
            return payload.decode(charset or "utf-8", errors="replace")
        except (LookupError, UnicodeDecodeError):
            return payload.decode("utf-8", errors="replace")

    def _extract_body(self, msg: mailbox.mboxMessage) -> str:
        """Extract plain text body from email message."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return self._safe_decode(payload, part.get_content_charset())
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return self._safe_decode(payload, part.get_content_charset())
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                return self._safe_decode(payload, msg.get_content_charset())
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
