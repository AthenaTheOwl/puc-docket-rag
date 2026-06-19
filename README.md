# PUC-DocketRAG

Full-text, citation-faithful searchable index of state-PUC dockets,
FERC filings, and rate cases, with structured extraction of
cost-allocation rules and load forecasts. The evidence layer behind
RatepayerExposure and SiteAtlas.

## What this is

A retrieval-augmented index over public regulatory filings. The first
slice covers PJM-zone state PUC dockets (VA, MD, NJ, PA, OH). Every
answer cites the docket page and line. Citation faithfulness is the
gate: a documented eval suite measures it at >= 95% recall and the CI
fails the build below the threshold.

The repo borrows the citation-faithful extraction pattern from
`supplier-risk-rag-agent`. It is deliberately a thin layer: ingest,
chunk, embed, FAISS, structured-extraction passes for two specific
schemas (cost-allocation rules, load forecasts). The search interface
is an Astro page; the API is a small FastAPI service.

## Status

v0 scaffold; no implementation yet. Spec 0002 lands the VA docket
ingester and the FAISS index. Spec 0003 lands the structured-extraction
passes. Spec 0004 lands the search interface.

## How to run

Will land in spec 0002. The expected shape:

```bash
uv sync
uv run pdr ingest --state VA --since 2024-01-01
uv run pdr index --state VA
uv run pdr extract --schema cost_allocation --state VA
uv run pdr serve
```

For v0 the only working command is `uv run pdr --help`.

## Layout

```
puc-docket-rag/
  src/pdr/
    ingest/
      pjm_state_dockets.py
    index/
      faiss_with_citations.py
    extraction/
      cost_allocation_rules.py
      load_forecasts.py
    api/
      search.py
    cli.py
  eval/
    citation_faithfulness.py
    fixtures/
  src/pages/
    search.astro
  data/
    dockets/                  # raw (gitignored)
    extracted/                # parsed structured output
  specs/0001-foundation/
  docs/first-pr.md
  AGENTS.md
  LICENSE
  README.md
```

## Citation faithfulness

The eval suite holds out a hand-labeled set of (question, answer,
expected-citation) tuples. A pipeline pass produces an answer and a
citation. The eval scores:

- **Recall@5**: does the expected citation appear in the top-5 cited
  passages?
- **Citation faithfulness**: does the produced answer's claim appear
  verbatim or as a paraphrase within the cited passage?

The threshold for v0 acceptance is recall@5 >= 90% and faithfulness
>= 95%. Drift below either fails CI.

## License

MIT. See LICENSE.
