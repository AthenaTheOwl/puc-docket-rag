# Tasks — 0002 Design (v0.1)

## Status

v0.1 shipped the local fixture-to-extraction vertical slice: VA fixture
loading, paragraph chunking, index build with citation sidecar, CLI search,
cost-allocation extraction, structural citation validation, config loading,
and README/local-run documentation.

Deferred scope remains in later specs:

- HTTP `POST /search` and the FastAPI service: spec 0003.
- Astro search page at `src/pages/search.astro`: spec 0003.
- `load_forecast` extraction: spec 0003.
- Labeled citation-faithfulness recall@5 / faithfulness eval suite: spec 0003.
- States beyond VA: spec 0004.

## PR 1 — Fixture + chunker + index

- [x] Add the VA docket fixture at
  `tests/fixtures/va/PUR-2024-00001/` with `fixture.meta.json`
  (source_url, retrieved_at, docket_id, sha256). If the PDF is not
  redistributable, commit `pages.jsonl` instead.
- [x] Add `src/pdr/ingest/fixture.py` implementing `load_fixture` for
  both PDF and `pages.jsonl` inputs. As built: shipped as flat module
  `src/pdr/ingest.py`; the sub-package layout is deferred to spec 0003+,
  matching the README Layout note.
- [x] Add `src/pdr/chunk/paragraph.py` implementing the 800/100
  paragraph-preferring splitter with NFC + whitespace-collapse
  normalization for `chunk_id` and 1-indexed `splitlines()` line
  numbers. As built: shipped as flat module `src/pdr/chunk.py` with
  `DEFAULT_TARGET_TOKENS = 800` and `DEFAULT_OVERLAP_TOKENS = 100`; the
  sub-package layout is deferred to spec 0003+, matching the README Layout
  note.
- [x] Wire `pdr chunk --fixture <path>` and write JSONL under
  `data/dockets/chunks/va/PUR-2024-00001.jsonl`.
- [x] Add `src/pdr/index/faiss_with_citations.py` and the `pdr index
  --fixture <path>` subcommand; write the `<stem>.index.json` sidecar
  holding `{chunks_sha256, embedding_model_id, config_hash}`. As built:
  shipped as flat module `src/pdr/index.py`; the sub-package layout is
  deferred to spec 0003+, matching the README Layout note.
- [x] Add pytest cases asserting every chunk row has non-empty
  `chunk_id`, `docket_id`, `page_number`, `line_start`, `line_end`.
  Verified by `tests/test_chunk.py::test_chunks_carry_all_citation_fields`.
- [x] Add a pytest case asserting `build_index` is a no-op when the
  three idempotency-key values are unchanged. Verified by
  `tests/test_search.py::test_index_is_idempotent`.

## PR 2 — Search CLI

- [x] Add `src/pdr/search/cli.py` and the `pdr search --query --k
  --index` subcommand. `--index` is a path stem; the loader appends
  `.faiss` and `.meta.jsonl`. As built: search logic shipped as flat module
  `src/pdr/search.py` and the subcommand is registered in `src/pdr/cli.py`;
  the sub-package layout is deferred to spec 0003+, matching the README
  Layout note.
- [x] Emit JSON to stdout with fields `chunk_id`, `docket_id`,
  `page_number`, `line_start`, `line_end`, `text`, `score`.
- [x] Add a pytest case asserting search against the indexed fixture
  returns at least one hit with all seven fields populated. Verified by
  `tests/test_search.py::test_search_returns_hits_with_all_seven_fields`.

## PR 3 — cost_allocation_rule extraction

- [x] Extend `schemas/cost_allocation_rule.schema.json` to add
  `chunk_id` to `source_citation`'s required fields.
- [x] Add an `LLMAdapter` interface under
  `src/pdr/extraction/_adapter.py` with a `FakeAdapter` for tests. As built:
  `LLMAdapter` and `FakeAdapter` shipped in flat module `src/pdr/extract.py`;
  the sub-package layout is deferred to spec 0003+, matching the README
  Layout note.
- [x] Add `src/pdr/extraction/cost_allocation_rules.py` and the
  `pdr extract --schema cost_allocation_rule --fixture <path>`
  subcommand; derive the index stem from the fixture path. As built:
  extraction logic shipped as flat module `src/pdr/extract.py` and the
  subcommand is registered in `src/pdr/cli.py`; the sub-package layout is
  deferred to spec 0003+, matching the README Layout note.
- [x] Add the citation-validation pass: drop rows whose
  `source_citation.chunk_id` is absent from the retrieved set. As built:
  implemented by `validate_citations` in `src/pdr/extract.py`.
- [x] Add a pytest case using `FakeAdapter` that one good row passes
  schema + citation validation and one row with a bogus `chunk_id` is
  dropped. Verified by
  `tests/test_search.py::test_extract_keeps_good_row_drops_bogus_citation`.

## Cross-cutting

- [x] Extend `.gitignore` to cover `data/dockets/chunks/`,
  `faiss_index/`, and `data/extracted/`.
- [x] Add `pdr.toml` with `chunk`, `index`, `embedding`, `extraction`
  sections and load it from `src/pdr/config.py`.
- [x] Update `README.md` "How to run" and the v0 status text to list
  the v0.1 commands and to flag HTTP, the Astro page, and
  `load_forecast` extraction as spec 0003.
