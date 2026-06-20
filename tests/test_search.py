"""Tests for the index + search + extract pipeline.

Builds an index from the committed VA fixture and exercises:

- top-K search returns hits with all seven fields populated
- a relevant query surfaces a chunk that mentions the query terms
- a second build with unchanged inputs is a no-op (idempotency sidecar)
- changing chunker config changes config_hash and forces a rebuild
- the extract pipeline drops rows whose chunk_id is not in the
  retrieved set and keeps rows whose chunk_id matches
- the on-disk layout uses ``<stem>.faiss`` + ``<stem>.meta.jsonl`` +
  ``<stem>.index.json``, matching spec 0002 design B3
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

from pdr.chunk import chunk_pages
from pdr.extract import FakeAdapter, extract, load_schema, validate_citations
from pdr.index import IndexConfig, build_index
from pdr.ingest import load_fixture
from pdr.search import search


FIXTURE = ROOT / "tests" / "fixtures" / "va" / "PUR-2024-00001"
HIT_FIELDS = {
    "chunk_id",
    "docket_id",
    "page_number",
    "line_start",
    "line_end",
    "text",
    "score",
}


def _build(tmp_path: Path, *, target_tokens: int = 800) -> Path:
    doc = load_fixture(FIXTURE)
    chunks = [
        c.to_jsonable()
        for c in chunk_pages(
            doc.pages(),
            docket_id=doc.docket_id,
            target_tokens=target_tokens,
        )
    ]
    stem = tmp_path / "va" / doc.docket_id
    cfg = IndexConfig(target_tokens=target_tokens)
    build_index(chunks, stem, config=cfg)
    return stem


def test_search_returns_hits_with_all_seven_fields(tmp_path):
    stem = _build(tmp_path)
    hits = search(stem, "data center cost allocation", k=5)
    assert hits, "expected at least one hit"
    for h in hits:
        d = h.to_jsonable()
        assert HIT_FIELDS == set(d.keys()), (
            f"missing fields: {HIT_FIELDS - set(d.keys())}"
        )
        for f in HIT_FIELDS - {"score"}:
            assert d[f] not in ("", None), f"field {f} must be populated"
        assert d["score"] > 0


def test_hits_carry_real_docket_id_from_fixture(tmp_path):
    stem = _build(tmp_path)
    hits = search(stem, "cost allocation methodology", k=3)
    assert hits
    for h in hits:
        assert h.docket_id == "PUR-2024-00001", (
            f"docket_id should come from fixture.meta.json, got {h.docket_id!r}"
        )


def test_relevant_query_surfaces_relevant_chunk(tmp_path):
    stem = _build(tmp_path)
    hits = search(stem, "twelve coincident peak generation allocation", k=3)
    assert hits
    blob = " ".join(h.text.lower() for h in hits)
    assert "12-cp" in blob or "coincident" in blob, (
        "expected the 12-CP discussion to appear in top hits"
    )


def test_index_on_disk_layout_uses_spec_suffixes(tmp_path):
    stem = _build(tmp_path)
    assert stem.with_suffix(".faiss").is_file(), (
        "spec 0002 acceptance: index payload must live at <stem>.faiss"
    )
    assert stem.with_suffix(".meta.jsonl").is_file()
    assert stem.with_suffix(".index.json").is_file()


def test_index_is_idempotent(tmp_path):
    doc = load_fixture(FIXTURE)
    chunks = [
        c.to_jsonable()
        for c in chunk_pages(doc.pages(), docket_id=doc.docket_id)
    ]
    stem = tmp_path / "va" / doc.docket_id
    first = build_index(chunks, stem, config=IndexConfig())
    assert first.written is True
    second = build_index(chunks, stem, config=IndexConfig())
    assert second.written is False, (
        "second build with unchanged inputs must be a no-op"
    )
    assert second.note == "no changes"
    sidecar = json.loads(stem.with_suffix(".index.json").read_text(encoding="utf-8"))
    assert sidecar["chunks_sha256"] == first.chunks_sha256
    assert sidecar["embedding_model_id"] == first.embedding_model_id
    assert sidecar["config_hash"] == first.config_hash


def test_index_rebuilds_when_config_changes(tmp_path):
    doc = load_fixture(FIXTURE)
    chunks = [
        c.to_jsonable()
        for c in chunk_pages(doc.pages(), docket_id=doc.docket_id)
    ]
    stem = tmp_path / "va" / doc.docket_id
    first = build_index(chunks, stem, config=IndexConfig(target_tokens=800))
    assert first.written
    second = build_index(chunks, stem, config=IndexConfig(target_tokens=400))
    assert second.written is True, "config_hash change must force rebuild"
    assert second.config_hash != first.config_hash


def test_index_rebuilds_when_embedding_model_changes(tmp_path):
    doc = load_fixture(FIXTURE)
    chunks = [
        c.to_jsonable()
        for c in chunk_pages(doc.pages(), docket_id=doc.docket_id)
    ]
    stem = tmp_path / "va" / doc.docket_id
    first = build_index(
        chunks, stem, config=IndexConfig(embedding_model_id="stdlib-tfidf-v1")
    )
    assert first.written
    swapped = build_index(
        chunks,
        stem,
        config=IndexConfig(embedding_model_id="sentence-transformers/all-MiniLM-L6-v2"),
    )
    assert swapped.written is True, (
        "embedding model swap must force rebuild (DEC-002)"
    )
    assert swapped.embedding_model_id != first.embedding_model_id


def test_extract_keeps_good_row_drops_bogus_citation(tmp_path):
    stem = _build(tmp_path)
    kept, dropped = extract(
        stem,
        "cost_allocation_rule",
        adapter=FakeAdapter(),
        query="cost allocation methodology",
        k=5,
    )
    assert len(kept) == 1
    assert kept[0]["rule_id"] == "CAR-001"
    assert len(dropped) == 1
    assert dropped[0][0]["rule_id"] == "CAR-002"
    reason = dropped[0][1]
    assert "not in retrieved set" in reason


def test_validate_citations_drops_schema_violations(tmp_path):
    stem = _build(tmp_path)
    hits = search(stem, "cost allocation methodology", k=3)
    bad_rows = [
        {"rule_id": "X", "rule_text": "missing source_citation"},
        {
            "rule_id": "Y",
            "rule_text": "page_number wrong type",
            "source_citation": {
                "docket_id": "PUR-2024-00001",
                "page_number": "one",
                "line_range": "1-2",
                "chunk_id": hits[0].chunk_id,
            },
        },
    ]
    kept, dropped = validate_citations(bad_rows, hits)
    assert kept == []
    assert len(dropped) == 2
    assert "missing field" in dropped[0][1]
    assert "must be integer" in dropped[1][1]


def test_cost_allocation_rule_schema_file_is_loadable():
    schema = load_schema("cost_allocation_rule")
    assert schema["title"] == "cost_allocation_rule"
    citation = schema["properties"]["source_citation"]
    assert "chunk_id" in citation["required"], (
        "spec 0002 R-PDR-V1-008: chunk_id is required on source_citation"
    )
    assert citation["properties"]["chunk_id"]["pattern"] == "^[0-9a-f]{40}$"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
