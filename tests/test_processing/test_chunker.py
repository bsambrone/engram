"""Tests for the text chunker."""

from engram.processing.chunker import _count_tokens, chunk_text


def test_short_text_single_chunk():
    text = "This is a short sentence."
    chunks = chunk_text(text, max_tokens=500)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_long_text_splits():
    # Build 100 sentences — should exceed 500 tokens
    sentences = [f"Sentence number {i} is about an interesting topic." for i in range(100)]
    text = " ".join(sentences)
    chunks = chunk_text(text, max_tokens=500, overlap_tokens=50)
    assert len(chunks) > 1
    # Recombining chunks should cover all original content
    combined = " ".join(chunks)
    for s in sentences:
        assert s in combined


def test_chunks_respect_size():
    sentences = [f"Sentence number {i} is about an interesting topic." for i in range(100)]
    text = " ".join(sentences)
    chunks = chunk_text(text, max_tokens=200, overlap_tokens=30)
    for chunk in chunks:
        token_count = _count_tokens(chunk)
        # Allow a small margin for sentence boundary — a single sentence
        # that exceeds max_tokens must be kept whole
        assert token_count <= 200 + 50, f"Chunk too large: {token_count} tokens"


def test_empty_text():
    assert chunk_text("") == [""]


def test_single_long_sentence():
    # A single sentence that exceeds max_tokens should still be returned
    long_sentence = "word " * 1000
    chunks = chunk_text(long_sentence.strip(), max_tokens=100, overlap_tokens=10)
    assert len(chunks) >= 1
    # The full content must be present
    combined = " ".join(chunks)
    assert "word" in combined
