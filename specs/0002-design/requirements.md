# Requirements — 0002 Design (v0.1)

## Scope

v0.1 is the data + retrieval layer for one VA PUC docket fixture
(`PUR-2024-00001`). It covers ingest of a single committed fixture,
chunking with citation fields, a FAISS index, a search CLI, and
structured extraction for `cost_allocation_rule`. The HTTP API, Astro
page, multi-state ingest, and `load_forecast` extraction are deferred.

## Functional requirements

- **R-PDR-V1-001** The repo SHALL ship a single VA PUC docket fixture
  with `docket_id = PUR-2024-00001` under
  `tests/fixtures/va/PUR-2024-00001/`, committed to git as a small
  redistributable PDF (or as a pre-extracted `pages.jsonl` if the source
  PDF is not redistributable). Refines R-PDR-001 to the v0.1
  single-docket scope.
- **R-PDR-V1-002** The fixture record SHALL carry `source_url`,
  `retrieved_at`, `docket_id`, and the SHA-256 of the original bytes in
  a sidecar `fixture.meta.json`. Carries R-PDR-002.
- **R-PDR-V1-003** `pdr chunk --fixture tests/fixtures/va/PUR-2024-00001`
  SHALL produce JSONL chunks each carrying `chunk_id`, `docket_id`,
  `page_number`, `line_start`, `line_end`, and `text`. `line_start` and
  `line_end` are 1-indexed line numbers in the page's extracted text as
  returned by `page_text.splitlines()`. Carries R-PDR-003.
- **R-PDR-V1-004** Chunk size SHALL target 800 tokens with 100-token
  overlap and SHALL prefer paragraph boundaries; short paragraphs MAY
  be merged and long paragraphs MAY be split when the size target
  cannot otherwise be met. A configuration flag MAY override the
  targets for tests.
- **R-PDR-V1-005** `pdr index --fixture <path>` SHALL build a FAISS
  index plus a parallel `meta.jsonl` keyed by FAISS integer ID; each
  meta row SHALL carry the chunk's `chunk_id` and citation fields.
  Carries R-PDR-004.
- **R-PDR-V1-006** The embedding model SHALL be selectable by config
  with a default that runs offline on CPU (sentence-transformers
  `all-MiniLM-L6-v2`). Model weights SHALL be cached under
  `$HF_HOME` (default `~/.cache/huggingface`) or under the
  `[embedding] cache_dir` path in `pdr.toml`. Network calls during
  `index` SHALL NOT be required after the first model download.
- **R-PDR-V1-007** `pdr search --query "<q>" --k <int> --index <stem>`
  SHALL return top-K hits to stdout as a JSON array. Each hit object
  SHALL carry `chunk_id`, `docket_id`, `page_number`, `line_start`,
  `line_end`, `text`, and `score`. `<stem>` is a path stem shared by
  the FAISS file and the `meta.jsonl` sidecar (e.g.
  `faiss_index/va/PUR-2024-00001`). Refines R-PDR-006 to a CLI; HTTP
  defers to spec 0003.
- **R-PDR-V1-008** `pdr extract --schema cost_allocation_rule
  --fixture <path>` SHALL derive the index stem from the fixture path
  by convention (`faiss_index/va/<docket_id>`), retrieve top-K
  passages via the search block, call the configured LLM, and emit
  JSONL whose every row validates against
  `schemas/cost_allocation_rule.schema.json`. Spec 0002 SHALL extend
  that schema's `source_citation` object to include a `chunk_id`
  field, and the extracted row's `source_citation.chunk_id` SHALL
  match a `chunk_id` returned by the retrieval call for that row.
  Refines R-PDR-005; drops `load_forecast` to spec 0003.
- **R-PDR-V1-009** Rows whose `source_citation.chunk_id` is absent
  from the retrieved set SHALL be dropped, not patched, and the
  failure SHALL be logged to stderr with the rule_id and the offending
  `chunk_id`.

## Non-functional requirements

- **R-PDR-V1-010** Raw downloaded dockets SHALL remain gitignored
  under `data/dockets/raw/`; only the curated fixture under
  `tests/fixtures/` is committed. Carries R-PDR-009.
- **R-PDR-V1-011** All prose surfaces added in v0.1, including the
  files under `specs/0002-design/`, SHALL pass
  `scripts/voice_lint.py`. Carries R-PDR-010.
- **R-PDR-V1-012** `uv run pdr chunk` and `uv run pdr index` SHALL be
  reproducible from a clean clone with no network access beyond the
  one-time embedding-model download into `$HF_HOME`; both SHALL be
  idempotent. The idempotency key for `index` SHALL combine
  `chunks.sha256`, the embedding model id, and a hash of the
  chunker + index config; a second run with an unchanged key SHALL
  be a no-op.

## Deferred

- HTTP `POST /search` and the FastAPI service → spec 0003.
- Astro page at `/search/` → spec 0003.
- `load_forecast` extraction → spec 0003.
- Citation-faithfulness eval suite and CI gate → spec 0003.
- States beyond VA → spec 0004.
