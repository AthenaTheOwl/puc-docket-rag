# Tasks — 0002 Design (v0.1)

## PR 1 — Fixture + chunker + index

- [ ] Add the VA docket fixture at
  `tests/fixtures/va/PUR-2024-00001/` with `fixture.meta.json`
  (source_url, retrieved_at, docket_id, sha256). If the PDF is not
  redistributable, commit `pages.jsonl` instead.
- [ ] Add `src/pdr/ingest/fixture.py` implementing `load_fixture` for
  both PDF and `pages.jsonl` inputs.
- [ ] Add `src/pdr/chunk/paragraph.py` implementing the 800/100
  paragraph-preferring splitter with NFC + whitespace-collapse
  normalization for `chunk_id` and 1-indexed `splitlines()` line
  numbers.
- [ ] Wire `pdr chunk --fixture <path>` and write JSONL under
  `data/dockets/chunks/va/PUR-2024-00001.jsonl`.
- [ ] Add `src/pdr/index/faiss_with_citations.py` and the `pdr index
  --fixture <path>` subcommand; write the `<stem>.index.json` sidecar
  holding `{chunks_sha256, embedding_model_id, config_hash}`.
- [ ] Add pytest cases asserting every chunk row has non-empty
  `chunk_id`, `docket_id`, `page_number`, `line_start`, `line_end`.
- [ ] Add a pytest case asserting `build_index` is a no-op when the
  three idempotency-key values are unchanged.

## PR 2 — Search CLI

- [ ] Add `src/pdr/search/cli.py` and the `pdr search --query --k
  --index` subcommand. `--index` is a path stem; the loader appends
  `.faiss` and `.meta.jsonl`.
- [ ] Emit JSON to stdout with fields `chunk_id`, `docket_id`,
  `page_number`, `line_start`, `line_end`, `text`, `score`.
- [ ] Add a pytest case asserting search against the indexed fixture
  returns at least one hit with all seven fields populated.

## PR 3 — cost_allocation_rule extraction

- [ ] Extend `schemas/cost_allocation_rule.schema.json` to add
  `chunk_id` to `source_citation`'s required fields.
- [ ] Add an `LLMAdapter` interface under
  `src/pdr/extraction/_adapter.py` with a `FakeAdapter` for tests.
- [ ] Add `src/pdr/extraction/cost_allocation_rules.py` and the
  `pdr extract --schema cost_allocation_rule --fixture <path>`
  subcommand; derive the index stem from the fixture path.
- [ ] Add the citation-validation pass: drop rows whose
  `source_citation.chunk_id` is absent from the retrieved set.
- [ ] Add a pytest case using `FakeAdapter` that one good row passes
  schema + citation validation and one row with a bogus `chunk_id` is
  dropped.

## Cross-cutting

- [ ] Extend `.gitignore` to cover `data/dockets/chunks/`,
  `faiss_index/`, and `data/extracted/`.
- [ ] Add `pdr.toml` with `chunk`, `index`, `embedding`, `extraction`
  sections and load it from `src/pdr/config.py`.
- [ ] Update `README.md` "How to run" and the v0 status text to list
  the v0.1 commands and to flag HTTP, the Astro page, and
  `load_forecast` extraction as spec 0003.
