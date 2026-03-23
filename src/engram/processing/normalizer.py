"""Text normalizer — strip HTML, normalize whitespace."""

import html
import re

from bs4 import BeautifulSoup


def normalize(text: str) -> str:
    """Normalize text by stripping HTML and cleaning whitespace.

    - Strips HTML tags and decodes entities if markup is detected
    - Decodes HTML entities (e.g. ``&amp;`` -> ``&``)
    - Collapses multiple spaces/tabs to a single space (preserves newlines)
    - Limits consecutive newlines to at most 2
    """
    # Strip HTML tags if present
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text()

    # Decode any remaining HTML entities (e.g. &amp; &lt; &#39;)
    text = html.unescape(text)

    # Collapse multiple horizontal whitespace characters to a single space
    text = re.sub(r"[^\S\n]+", " ", text)

    # Limit consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
