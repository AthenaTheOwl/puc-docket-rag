# DEC-001 — citation-faithfulness contract

- status: accepted
- date: 2026-06-20
- scope: spec 0002 v0.1 (one VA docket fixture, stdlib-only pipeline)
- supersedes: none

## decision

For v0.1, an extracted row is "citation-faithful" iff its
`source_citation.chunk_id` matches a `chunk_id` returned by the
retrieval call that produced the row. The check is structural, not
semantic: the system does not verify that the chunk text supports the
claim, only that the citation resolves to a real, retrieved chunk.

Rows that fail the check are dropped, not patched. The drop is logged
to stderr with the rule_id and the offending chunk_id. The kept-rows
JSONL is what callers consume; the dropped set is observational.

## why

The downstream consumers (RatepayerExposure, SiteAtlas) treat every
extracted row as an assumption with provenance. A row whose citation
does not resolve to a retrieved chunk is worse than no row: it
introduces a fabricated source into the assumption graph and breaks the
audit trail. Dropping is conservative; patching would invent
provenance.

Spec 0002 deliberately does not gate on semantic faithfulness ("does
the chunk text actually support the claim"). That eval is a labeled
recall@5 + faithfulness suite and ships with spec 0003+. v0.1 makes the
weaker, mechanical guarantee so the pipeline is safe to wire up before
the eval lands.

## scope and non-scope

In scope for v0.1:

- The chunk_id used in the citation is the v0.1 chunk_id:
  `sha1(normalized_text + ":" + str(page_number))`, with normalization
  = NFC + whitespace collapse + strip. This is stable across
  whitespace-only edits to the source text.
- The retrieved set is the top-K passages returned by `pdr search` for
  the seed query used during extraction.
- The validation pass runs inside `pdr extract`; it is not a separate
  CLI in v0.1.

Out of scope for v0.1, deferred to spec 0003+:

- Semantic faithfulness (does the chunk text support the claim text).
- Labeled recall@5 and faithfulness gates in CI.
- Citations across multiple retrieval calls per row.
- Citations that point to a span (line_start/line_end) tighter than the
  chunk; the row carries the chunk's line range as a coarse pointer.

## implementation pointers

- `src/pdr/extract.py::validate_citations` enforces the contract.
- `src/pdr/chunk.py::chunk_id_for` defines the normalized chunk_id.
- `tests/test_search.py::test_extract_keeps_good_row_drops_bogus_citation`
  is the contract test: one good row passes, one row with a fabricated
  chunk_id is dropped.

## consequences

- The v0.1 extraction output is small (rows are dropped, not patched)
  and the drop rate is a useful signal: a high drop rate means the
  LLM is hallucinating citations and the prompt or the retrieval set
  needs work.
- Swapping the embedding/index engine from stdlib TF-IDF to FAISS +
  sentence-transformers in spec 0003 does not change the contract:
  chunk_ids are computed from normalized text and survive the swap.
- The eval suite in spec 0003 will layer semantic faithfulness on top
  of this structural check, not replace it.
