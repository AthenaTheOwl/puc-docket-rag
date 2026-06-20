"""Paragraph-preferring chunker.

v0.1 uses whitespace tokenization as a stdlib stand-in for tiktoken
``cl100k_base``. The 800/100 target and overlap are honored as a token
budget; ``chunk_id`` normalization (NFC + whitespace collapse) is exact
so chunk identity is stable across whitespace-only edits and survives
the swap to tiktoken in spec 0003+.

Line numbers are tracked from the source page's paragraph spans rather
than recovered by substring search after packing: a chunk that begins
with a carry-overlap tail from the previous chunk would otherwise fail
to locate itself byte-for-byte in the source and silently collapse to
``(1, max_line)``. The carry text is prepended for retrieval continuity
but does not influence the chunk's reported line range.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Iterable, Iterator


DEFAULT_TARGET_TOKENS = 800
DEFAULT_OVERLAP_TOKENS = 100
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    docket_id: str
    page_number: int
    line_start: int
    line_end: int
    text: str

    def to_jsonable(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class _Paragraph:
    line_start: int
    line_end: int
    text: str


def normalize_text(text: str) -> str:
    nfc = unicodedata.normalize("NFC", text)
    collapsed = _WHITESPACE.sub(" ", nfc)
    return collapsed.strip()


def chunk_id_for(text: str, page_number: int) -> str:
    payload = f"{normalize_text(text)}:{page_number}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _count_tokens(text: str) -> int:
    return len(text.split())


def _split_paragraphs(page_text: str) -> list[_Paragraph]:
    """Split page_text into paragraphs with their source line spans.

    A paragraph is a maximal run of non-empty lines, delimited by blank
    lines. Line numbers are 1-indexed and refer to
    ``page_text.splitlines()``.
    """
    lines = page_text.splitlines()
    out: list[_Paragraph] = []
    buf: list[str] = []
    buf_start: int | None = None
    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            if buf and buf_start is not None:
                out.append(
                    _Paragraph(buf_start, buf_start + len(buf) - 1, "\n".join(buf))
                )
            buf = []
            buf_start = None
        else:
            if buf_start is None:
                buf_start = i
            buf.append(line)
    if buf and buf_start is not None:
        out.append(_Paragraph(buf_start, buf_start + len(buf) - 1, "\n".join(buf)))
    return out


def _tail_tokens(text: str, n: int) -> str:
    if n <= 0:
        return ""
    toks = text.split()
    if len(toks) <= n:
        return text
    return " ".join(toks[-n:])


def _force_split_sentences(para_text: str, target: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", para_text)
    out: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for sent in sentences:
        st = _count_tokens(sent)
        if buf and buf_tokens + st > target:
            out.append(" ".join(buf))
            buf = [sent]
            buf_tokens = st
        else:
            buf.append(sent)
            buf_tokens += st
    if buf:
        out.append(" ".join(buf))
    return out


def _pack_paragraphs(
    paragraphs: list[_Paragraph], target: int, overlap: int
) -> list[tuple[int, int, str]]:
    """Greedy pack: accumulate paragraphs until the next one would exceed
    the target, then emit. The carry-overlap is the previous chunk's
    last ``overlap`` tokens and is prepended to the next chunk's text;
    it does not contribute to the next chunk's line range.

    Returns ``[(line_start, line_end, text)]`` triples. ``line_start`` /
    ``line_end`` are the min/max source-line of the real paragraphs that
    landed in the chunk.
    """
    if not paragraphs:
        return []
    chunks: list[tuple[int, int, str]] = []
    buf: list[_Paragraph] = []
    buf_tokens = 0
    carry = ""

    def _flush() -> None:
        nonlocal buf, buf_tokens, carry
        if not buf:
            return
        body = "\n\n".join(p.text for p in buf)
        text = f"{carry}\n\n{body}" if carry else body
        cs = min(p.line_start for p in buf)
        ce = max(p.line_end for p in buf)
        chunks.append((cs, ce, text))
        carry = _tail_tokens(text, overlap)
        buf = []
        buf_tokens = 0

    for para in paragraphs:
        para_tokens = _count_tokens(para.text)
        if para_tokens > target * 4:
            _flush()
            for sp in _force_split_sentences(para.text, target):
                text = f"{carry} {sp}".strip() if carry else sp
                chunks.append((para.line_start, para.line_end, text))
                carry = _tail_tokens(text, overlap)
            continue
        prospective = buf_tokens + para_tokens
        if buf and prospective > target:
            _flush()
            buf = [para]
            buf_tokens = para_tokens
        else:
            buf.append(para)
            buf_tokens += para_tokens
    _flush()
    return chunks


def chunk_pages(
    pages: Iterable[tuple[int, str]],
    *,
    docket_id: str,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> Iterator[Chunk]:
    """Emit ``Chunk`` records from ``(page_number, page_text)`` tuples.

    Line numbers come from the packed paragraphs' source-line spans;
    carry-overlap text prepended for retrieval continuity does not shift
    the reported ``line_start`` / ``line_end``.
    """
    for page_number, page_text in pages:
        paragraphs = _split_paragraphs(page_text)
        packed = _pack_paragraphs(paragraphs, target_tokens, overlap_tokens)
        for line_start, line_end, text in packed:
            yield Chunk(
                chunk_id=chunk_id_for(text, page_number),
                docket_id=docket_id,
                page_number=page_number,
                line_start=line_start,
                line_end=line_end,
                text=text,
            )
