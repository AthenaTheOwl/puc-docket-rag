# First PR after the scaffold

Narrow scope: schemas, voice and schema validators, CLI skeleton. No
ingester yet.

## Title

`feat: pdr CLI skeleton, extraction schemas, voice + schema gates`

## Files changed

- `pyproject.toml` (new) — defines the `pdr` console script and the
  Python dependencies (FAISS, FastAPI, jsonschema). No model
  dependencies yet; those land with the indexer in PR 3.
- `src/pdr/cli.py` (new) — argparse-driven CLI exposing the planned
  subcommands (`ingest`, `chunk`, `index`, `extract`, `serve`, `eval`)
  as stubs that print "not implemented (spec 0002)" and exit zero.
- `schemas/cost_allocation_rule.schema.json` (new) — JSON Schema
  draft 2020-12 with required fields: `rule_id`, `jurisdiction`,
  `effective_date`, `allocator`, `affected_customer_classes`,
  `source_citation` (object with `docket_id`, `page_number`,
  `line_range`).
- `schemas/load_forecast.schema.json` (new) — Required fields:
  `forecast_id`, `jurisdiction`, `forecast_horizon_years`,
  `projected_load_mw`, `source_citation`.
- `scripts/validate_schemas.py` (new) — parses both schemas with
  `jsonschema.Draft202012Validator.check_schema`.
- `scripts/voice_lint.py` (new) — copied from sports-prediction-os.
- `Makefile` (new) — `make validate` runs both scripts.

## Verification

```bash
uv sync
make validate
uv run pdr --help
uv run pdr ingest --state VA --since 2024-01-01
```

Expected:
```
make validate
  voice_lint: OK
  validate_schemas: OK (2 schemas)
pdr --help
  ... lists six subcommands ...
pdr ingest ...
  not implemented (spec 0002)
```

Zero exit codes throughout.

A reviewer should ask whether the two extraction schemas cover the
downstream consumers' actual needs. If RatepayerExposure or SiteAtlas
needs a third schema, name it now rather than retrofitting.

## What this PR does NOT do

- No ingester; PR 2.
- No chunker; PR 2.
- No FAISS index; PR 3.
- No API; PR 3.
- No eval suite; PR 3.
- No GitHub Action.
