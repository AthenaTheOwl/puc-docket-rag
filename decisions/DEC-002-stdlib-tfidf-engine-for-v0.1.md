# DEC-002 — stdlib TF-IDF engine for v0.1; FAISS swap deferred

- status: accepted
- date: 2026-06-20
- scope: spec 0002 v0.1 (one VA docket fixture, retrieval engine)
- supersedes: none
- supersedes-by-future: spec 0003 engine swap (planned)

## decision

v0.1 ships a pure-stdlib TF-IDF retrieval engine instead of the FAISS +
`sentence-transformers` (`all-MiniLM-L6-v2`) engine described in design
B3 and required by R-PDR-V1-006. The on-disk layout, CLI surface,
meta-row schema, and idempotency-sidecar keys stay exactly as design B3
specifies (`<stem>.faiss`, `<stem>.meta.jsonl`, `<stem>.index.json`); only
the engine that fills `<stem>.faiss` changes.

The embedding-model identifier in the sidecar is `stdlib-tfidf-v1` for
v0.1; the swap to `sentence-transformers/all-MiniLM-L6-v2` in spec 0003
will flip that field and force a one-time rebuild via the existing
idempotency machinery.

## why

The v0.1 task is to land an auditable vertical slice in one PR with no
heroics. Hard-requiring FAISS in the first slice would force:

- a wheel install path (FAISS lacks a clean pure-Python fallback), and
- a one-time `all-MiniLM-L6-v2` download (~90 MB) before the test suite
  could run from a clean clone.

Neither is a great fit for the v0.1 acceptance gate, which expects
`uv run pytest` to pass from a clean clone with no network beyond the
embedding-model download. Pushing the swap to spec 0003 lets the v0.1
slice prove the contract (citation-faithful chunks, idempotent index,
search + extract end to end) without bundling a model wheel into the
first PR.

The TF-IDF engine is good enough for the v0.1 demonstration. The
fixture has four pages, ~16 chunks at default config; lexical retrieval
hits the expected `12-CP` / `cost allocation` passages with cosine
scores well above the noise floor.

## what stays the same across the swap

- The chunk_id contract from DEC-001 (NFC + whitespace-collapse + page
  number, SHA-1 hex) is engine-agnostic and survives the swap.
- The on-disk path stem stays `<stem>` with `.faiss`, `.meta.jsonl`, and
  `.index.json` siblings. Callers do not change.
- The idempotency sidecar still carries `chunks_sha256`,
  `embedding_model_id`, and `config_hash`. Flipping `embedding_model_id`
  from `stdlib-tfidf-v1` to `sentence-transformers/all-MiniLM-L6-v2`
  forces a rebuild on the first spec-0003 run; no migration script
  needed.
- The search CLI surface (`pdr search --query --k --index`) is
  unchanged.
- The citation-faithfulness contract (DEC-001) is engine-agnostic; a
  retrieved chunk is still identified by its `chunk_id`, not by its
  vector.

## what changes in spec 0003

- Add `sentence-transformers` and `faiss-cpu` to `[project]`
  `dependencies` in `pyproject.toml`.
- Replace the JSON-encoded TF-IDF payload at `<stem>.faiss` with the
  binary FAISS `IndexFlatIP` payload.
- Replace `pdr.index._write_vectors` / `_load_vectors` with FAISS
  serialization.
- Replace `pdr.search._query_vector` / `_cosine` with FAISS query.
- Wire `[embedding] model_id` and `[embedding] cache_dir` from
  `pdr.toml` into the index pipeline. v0.1 reads but does not consume
  these values.
- Flip the embedding-model identifier in the sidecar; the existing
  idempotency check forces a one-time rebuild.

## test invariants that survive the swap

- `test_chunks_carry_all_citation_fields` — chunk-side, not engine-side.
- `test_chunk_id_is_stable_across_whitespace_edits` — chunk-side.
- `test_index_is_idempotent` — exercises the sidecar contract that the
  swap preserves.
- `test_index_rebuilds_when_config_changes` — exercises the sidecar
  contract.
- `test_extract_keeps_good_row_drops_bogus_citation` — citation
  contract is engine-agnostic.

The lexical-affinity test
(`test_relevant_query_surfaces_relevant_chunk`) asserts that the
top hits for the seed query contain `12-CP` or `coincident`; this is
satisfied by both engines on the fixture.

## consequences

- v0.1 is reproducible from a clean clone with zero network access. The
  R-PDR-V1-006 "one-time embedding download" bullet does not fire in
  v0.1 because the engine is stdlib.
- The `<stem>.faiss` file in v0.1 is JSON-formatted; anyone inspecting
  it will see a JSON object, not FAISS bytes. The module docstring and
  this decision document the gap.
- Spec 0003 inherits the rebuild on its first run for free.
