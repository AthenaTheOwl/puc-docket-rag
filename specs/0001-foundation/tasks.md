# Tasks — 0001 Foundation

## PR 1 — Schemas + voice gate + CLI skeleton

- [ ] Add `pyproject.toml` with `pdr` console script
- [ ] Implement `pdr --help` listing the planned subcommands
- [ ] Add `schemas/cost_allocation_rule.schema.json`
- [ ] Add `schemas/load_forecast.schema.json`
- [ ] Add `scripts/validate_schemas.py`
- [ ] Add `scripts/voice_lint.py` copied from sports-prediction-os
- [ ] Add `Makefile` with `validate` target

## PR 2 — VA ingester + chunker

- [ ] Implement `pdr ingest --state VA --since DATE`
- [ ] Implement `pdr chunk --state VA` with citation fields per
  R-PDR-003
- [ ] Add fixtures (5 small public VA docket PDFs)
- [ ] Add pytest cases asserting chunk citation fields are populated
- [ ] Document the gitignore rule for `data/dockets/raw/`

## PR 3 — FAISS index + search API

- [ ] Implement `pdr index --state VA`
- [ ] Implement `pdr serve` exposing `POST /search`
- [ ] Add a smoke test hitting the API against the fixtures
- [ ] Add `eval/fixtures/` with 10 hand-labeled (query, expected
  citation) tuples
- [ ] Implement `eval/citation_faithfulness.py` and the threshold
  gate
- [ ] Confirm `uv run pdr eval citation-faithfulness` exits zero
  against the fixtures

## Out of scope for foundation

- [ ] States beyond VA (spec 0003)
- [ ] Structured extraction (spec 0003)
- [ ] Astro search page (spec 0004)
- [ ] Public hosting (separate repo)
