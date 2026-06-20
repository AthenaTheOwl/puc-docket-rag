# Acceptance — 0002 Design (v0.1)

## What v0.1 done means

- The VA docket fixture lives at
  `tests/fixtures/va/PUR-2024-00001/` with `fixture.meta.json` and
  either a PDF or a `pages.jsonl`.
- `pdr chunk --fixture <path>` writes a JSONL with every chunk
  carrying `chunk_id`, `docket_id`, `page_number`, `line_start`,
  `line_end`, `text`.
- `pdr index --fixture <path>` builds a FAISS file plus a parallel
  `meta.jsonl` and a `.index.json` idempotency sidecar; a second run
  with unchanged inputs prints `no changes` and exits zero.
- `pdr search --query "<q>" --k 5 --index <stem>` returns a JSON
  array on stdout; each hit carries `chunk_id`, `docket_id`,
  `page_number`, `line_start`, `line_end`, `text`, and `score`.
- `pdr extract --schema cost_allocation_rule --fixture <path>` writes
  a JSONL whose every row validates against the schema and whose every
  row's `source_citation.chunk_id` matches a `chunk_id` returned by
  the retrieval call.

## Commands to run on a fresh clone

```bash
git clone <repo>
cd puc-docket-rag
uv sync

# voice + schema gates
python scripts/voice_lint.py docs/ specs/
python scripts/validate_schemas.py

# chunk + index against the committed VA fixture
FIXTURE=tests/fixtures/va/PUR-2024-00001
uv run pdr chunk --fixture "$FIXTURE"
uv run pdr index --fixture "$FIXTURE"

# idempotency: second index call writes nothing new
uv run pdr index --fixture "$FIXTURE"   # expect "no changes"

# search (note: --index takes the path stem, not a directory)
uv run pdr search \
  --query "data-center cost allocation" \
  --k 5 \
  --index faiss_index/va/PUR-2024-00001 \
  | jq '.[0] | {chunk_id, docket_id, page_number, line_start, line_end, score}'

# structured extraction (uses FakeAdapter unless PDR_LLM is set)
PDR_LLM=fake uv run pdr extract \
  --schema cost_allocation_rule \
  --fixture "$FIXTURE"

# unit tests
uv run pytest
```

Expected: zero exit codes throughout; `pdr search` prints at least one
hit with citation fields populated; the extraction JSONL is well-formed
and each row passes schema + citation validation.

## Gates to pass

- `scripts/voice_lint.py` — no banned terms in v0.1 prose, including
  the files under `specs/0002-design/`.
- `scripts/validate_schemas.py` — `cost_allocation_rule.schema.json`
  (extended with `chunk_id`) parses.
- `uv run pytest` — chunker, indexer idempotency, search, and
  extraction tests pass.
- `uv run pdr index` second invocation is a no-op (asserted by test).

## Out of scope for v0.1 acceptance

- HTTP `POST /search` and the FastAPI service (spec 0003).
- The Astro page at `src/pages/search.astro` (spec 0003).
- `load_forecast` extraction (spec 0003).
- Citation-faithfulness recall@5 / faithfulness CI gate (spec 0003).
- States beyond VA (spec 0004).
- LLM-graded faithfulness; v0.1 only checks that citations resolve to
  real chunks.
