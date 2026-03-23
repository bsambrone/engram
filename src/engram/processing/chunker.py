"""Sentence-aware text chunker with token counting via tiktoken."""

import re

import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    """Count the number of tokens in *text* using cl100k_base encoding."""
    return len(_enc.encode(text))


def chunk_text(
    text: str,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[str]:
    """Split *text* into chunks that each fit within *max_tokens*.

    Splitting is sentence-aware: chunks are built by accumulating whole
    sentences.  When a chunk would exceed *max_tokens*, a new chunk is
    started with ~overlap_tokens of trailing context from the previous
    chunk for continuity.

    If the entire text fits in one chunk it is returned as-is (single-element
    list).  An empty string is returned as ``[""]``.
    """
    if not text:
        return [text]

    if _count_tokens(text) <= max_tokens:
        return [text]

    # Split on sentence boundaries (after . ! ?)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    # If we only got one "sentence" that exceeds max_tokens, fall back to
    # word-level splitting so we can still produce multiple chunks.
    if len(sentences) == 1:
        return _chunk_by_words(text, max_tokens, overlap_tokens)

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _count_tokens(sentence)

        if current_tokens + sentence_tokens > max_tokens and current_sentences:
            # Flush current chunk
            chunks.append(" ".join(current_sentences))

            # Build overlap from the tail of current_sentences
            overlap_sents: list[str] = []
            overlap_tok = 0
            for s in reversed(current_sentences):
                s_tok = _count_tokens(s)
                if overlap_tok + s_tok > overlap_tokens:
                    break
                overlap_sents.insert(0, s)
                overlap_tok += s_tok

            current_sentences = list(overlap_sents)
            current_tokens = overlap_tok

        current_sentences.append(sentence)
        current_tokens += sentence_tokens

    # Final chunk
    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks


def _chunk_by_words(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Fallback: chunk a single long block by words."""
    words = text.split()
    chunks: list[str] = []
    start = 0

    while start < len(words):
        # Binary-search-ish: grow until we exceed max_tokens
        end = start + 1
        while end <= len(words):
            candidate = " ".join(words[start:end])
            if _count_tokens(candidate) > max_tokens:
                break
            end += 1
        # end-1 is the last index that fit (or end if we reached the end)
        if end - 1 == start:
            # Single word exceeds max_tokens — include it anyway
            end = start + 2
        else:
            end = end - 1

        chunk = " ".join(words[start:end])
        chunks.append(chunk)

        # Advance with overlap
        overlap_start = end
        overlap_toks = 0
        for i in range(end - 1, start - 1, -1):
            w_tok = _count_tokens(words[i])
            if overlap_toks + w_tok > overlap_tokens:
                break
            overlap_start = i
            overlap_toks += w_tok
        start = overlap_start if overlap_start > start else end

    return chunks
