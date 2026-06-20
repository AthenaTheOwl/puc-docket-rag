"""Tests for the ingest + paragraph chunker.

Exercises the committed fixture under
``tests/fixtures/va/PUR-2024-00001/``:

- pagination yields the four pages declared in pages.jsonl
- every chunk carries the six citation fields, non-empty
- chunk_id is stable across whitespace-only edits (NFC + collapse)
- chunk_id changes when the page number changes
- small target_tokens forces more than one chunk per page
- line_start / line_end actually bracket the chunk's content in the
  source page, even when the chunk begins with a carry-overlap tail
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdr.chunk import (
    _split_paragraphs,
    chunk_id_for,
    chunk_pages,
    normalize_text,
)
from pdr.ingest import load_fixture


FIXTURE = ROOT / "tests" / "fixtures" / "va" / "PUR-2024-00001"
PAGES_JSONL = FIXTURE / "pages.jsonl"


def test_fixture_exists_and_is_small():
    assert PAGES_JSONL.is_file(), f"missing fixture at {PAGES_JSONL}"
    size = PAGES_JSONL.stat().st_size
    assert 1_000 < size < 10_000, f"fixture must be <10KB (got {size} bytes)"
    meta = FIXTURE / "fixture.meta.json"
    assert meta.is_file(), f"missing fixture.meta.json at {meta}"
    data = json.loads(meta.read_text(encoding="utf-8"))
    for field in ("docket_id", "source_url", "retrieved_at", "sha256"):
        assert data.get(field), f"fixture.meta.json: missing {field}"


def test_load_fixture_derives_docket_id_from_meta():
    doc = load_fixture(FIXTURE)
    assert doc.docket_id == "PUR-2024-00001"
    assert doc.meta["source_url"]
    assert doc.meta["retrieved_at"]


def test_fixture_paginates_to_multiple_pages():
    doc = load_fixture(FIXTURE)
    pages = list(doc.pages())
    assert len(pages) == 4, f"expected 4 pages, got {len(pages)}"
    page_numbers = [p for p, _ in pages]
    assert page_numbers == [1, 2, 3, 4]
    for _, text in pages:
        assert text.strip() != ""


def test_chunks_carry_all_citation_fields():
    doc = load_fixture(FIXTURE)
    chunks = list(
        chunk_pages(doc.pages(), docket_id=doc.docket_id, target_tokens=800)
    )
    assert chunks, "chunker produced zero chunks"
    for c in chunks:
        assert c.chunk_id and len(c.chunk_id) == 40, "chunk_id must be sha1 hex"
        assert c.docket_id == "PUR-2024-00001"
        assert c.page_number >= 1
        assert c.line_start >= 1
        assert c.line_end >= c.line_start
        assert c.text.strip() != ""


def test_chunk_id_is_stable_across_whitespace_edits():
    a = "The Company  submits   this\npetition.\n"
    b = "The Company submits this petition.\n"
    assert chunk_id_for(a, 1) == chunk_id_for(b, 1)


def test_chunk_id_changes_with_page_number():
    a = "Same paragraph text."
    assert chunk_id_for(a, 1) != chunk_id_for(a, 2)


def test_normalize_text_handles_nfc():
    composed = "café"
    decomposed = "café"
    assert normalize_text(composed) == normalize_text(decomposed)


def test_small_target_forces_multiple_chunks_per_page():
    doc = load_fixture(FIXTURE)
    chunks = list(
        chunk_pages(
            doc.pages(),
            docket_id=doc.docket_id,
            target_tokens=40,
            overlap_tokens=5,
        )
    )
    by_page: dict[int, int] = {}
    for c in chunks:
        by_page[c.page_number] = by_page.get(c.page_number, 0) + 1
    assert max(by_page.values()) >= 2, (
        f"a small target_tokens should produce >1 chunk per page, "
        f"got per-page counts {by_page}"
    )


def test_chunks_are_unique_by_id():
    doc = load_fixture(FIXTURE)
    chunks = list(
        chunk_pages(doc.pages(), docket_id=doc.docket_id, target_tokens=800)
    )
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk_ids must be unique"


def test_line_ranges_bracket_chunk_content_under_carry_overlap():
    """Even when a chunk begins with a carry-overlap tail (which would
    not match the source page byte-for-byte), its line_start / line_end
    must bracket at least one paragraph in the source page.
    """
    doc = load_fixture(FIXTURE)
    pages_by_no = dict(doc.pages())
    chunks = list(
        chunk_pages(
            doc.pages(),
            docket_id=doc.docket_id,
            target_tokens=40,
            overlap_tokens=5,
        )
    )
    page_lines: dict[int, list[str]] = {
        n: t.splitlines() for n, t in pages_by_no.items()
    }
    for c in chunks:
        lines = page_lines[c.page_number]
        assert 1 <= c.line_start <= len(lines), (
            f"line_start {c.line_start} out of range for page "
            f"{c.page_number} (1..{len(lines)})"
        )
        assert c.line_start <= c.line_end <= len(lines), (
            f"line_end {c.line_end} out of range for page "
            f"{c.page_number} (line_start={c.line_start}, max={len(lines)})"
        )
        snippet = "\n".join(lines[c.line_start - 1 : c.line_end])
        first_token = snippet.split()[:1]
        assert first_token, "bracketed snippet must be non-empty"
        assert first_token[0] in c.text, (
            f"chunk {c.chunk_id} does not contain the first token "
            f"of its bracketed source lines: {first_token[0]!r}"
        )


def test_split_paragraphs_carries_source_line_spans():
    page = "alpha line\nstill alpha\n\nbeta line\n\ngamma\n"
    paras = _split_paragraphs(page)
    assert [(p.line_start, p.line_end) for p in paras] == [
        (1, 2),
        (4, 4),
        (6, 6),
    ]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
