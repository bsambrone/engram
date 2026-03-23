"""Tests for the text normalizer."""

from engram.processing.normalizer import normalize


def test_strip_html():
    raw = "<p>Hello <b>world</b></p>"
    assert normalize(raw) == "Hello world"


def test_normalize_whitespace():
    # Multiple spaces collapse to one
    assert normalize("hello   world") == "hello world"
    # Multiple newlines collapse to max 2
    assert normalize("a\n\n\n\nb") == "a\n\nb"


def test_decode_entities():
    assert normalize("&amp;") == "&"
    assert normalize("&lt;b&gt;bold&lt;/b&gt;") == "<b>bold</b>"


def test_preserve_content():
    text = "This is a normal sentence."
    assert normalize(text) == text


def test_strip_nested_html():
    raw = "<div><p>Nested <span>content</span></p></div>"
    assert normalize(raw) == "Nested content"


def test_mixed_whitespace():
    text = "hello\t\t  world\n\n\n\n\nfoo"
    result = normalize(text)
    assert "  " not in result.replace("\n", "")
    assert "\n\n\n" not in result
