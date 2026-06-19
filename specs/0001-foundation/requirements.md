# Requirements — 0001 Foundation

## Functional requirements

- **R-PDR-001** The repo SHALL ingest state-PUC dockets from VA, MD,
  NJ, PA, OH; the first ingester SHALL cover VA.
- **R-PDR-002** Each ingested document SHALL be stored with a
  `source_url`, `retrieved_at`, `docket_id`, and a SHA-256 of its
  bytes.
- **R-PDR-003** Documents SHALL be chunked with each chunk carrying
  `docket_id`, `page_number`, `line_start`, `line_end`.
- **R-PDR-004** The repo SHALL build a FAISS index over chunk
  embeddings; each indexed vector SHALL retain the chunk's citation
  fields.
- **R-PDR-005** The repo SHALL ship structured-extraction passes for
  two schemas: `cost_allocation_rule` and `load_forecast`. Output is
  JSON with citations to source passages.
- **R-PDR-006** The repo SHALL ship a search API exposing
  `POST /search` returning the top-K passages with citations.
- **R-PDR-007** The repo SHALL ship an Astro page at `/search/`
  consuming the API.
- **R-PDR-008** A citation-faithfulness eval suite SHALL be
  implemented; the v0 acceptance thresholds are recall@5 >= 90% and
  faithfulness >= 95%.

## Non-functional requirements

- **R-PDR-009** Ingested raw documents SHALL be gitignored;
  `data/dockets/raw/` is local-only.
- **R-PDR-010** All prose surfaces SHALL pass
  `scripts/voice_lint.py`.
- **R-PDR-011** Structured-extraction output SHALL validate against
  JSON Schemas at `schemas/cost_allocation_rule.schema.json` and
  `schemas/load_forecast.schema.json`.
- **R-PDR-012** The full ingest-and-index pass for a single state
  SHALL be reproducible from a clean clone given valid network
  access; intermediate caches make subsequent runs incremental.
