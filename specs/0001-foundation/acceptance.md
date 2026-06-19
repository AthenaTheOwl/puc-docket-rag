# Acceptance — 0001 Foundation

## What v0 done means

- `pdr ingest --state VA --since 2024-01-01` pulls and caches at
  least five docket PDFs.
- `pdr chunk --state VA` produces a JSONL with citation fields
  populated.
- `pdr index --state VA` builds a FAISS index and a parallel
  `meta.jsonl`.
- `pdr serve` exposes `POST /search` returning passages with
  citations.
- `pdr eval citation-faithfulness` exits zero against the 10-fixture
  eval suite, with recall@5 >= 90% and faithfulness >= 95%.

## Commands to run

```bash
git clone <repo>
cd puc-docket-rag
uv sync
make validate
uv run pdr ingest --state VA --since 2024-01-01
uv run pdr chunk --state VA
uv run pdr index --state VA
uv run pdr serve &
SERVE_PID=$!
sleep 2
curl -s -X POST http://127.0.0.1:8000/search \
  -H 'content-type: application/json' \
  -d '{"query": "data-center cost allocation"}' | jq .
kill $SERVE_PID
uv run pdr eval citation-faithfulness
```

Expected: zero exit codes throughout; the search response carries at
least one passage with citation fields; the eval exits zero.

## Gates to pass

- `scripts/voice_lint.py` — no banned terms.
- `scripts/validate_schemas.py` — both extraction schemas parse.
- `pdr eval citation-faithfulness` — recall@5 >= 90%, faithfulness
  >= 95%.
- `uv run pytest` — chunker and API smoke tests pass.

## Out of scope for acceptance

- Structured extraction passes (spec 0003).
- Astro search page (spec 0004).
- States beyond VA.
- LLM-graded faithfulness (manual scoring is sufficient for v0).
