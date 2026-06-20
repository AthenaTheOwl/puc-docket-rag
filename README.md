# PUC-DocketRAG

Full-text, citation-faithful searchable index of state-PUC dockets,
FERC filings, and rate cases, with structured extraction of
cost-allocation rules and load forecasts. The evidence layer behind
RatepayerExposure and SiteAtlas.

## what this is

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

## status

v0.1 ships the vertical slice for one VA docket fixture
(`PUR-2024-00001`): chunk, index, search, and `cost_allocation_rule`
extraction with citation validation. The HTTP API, the Astro search
page, and `load_forecast` extraction defer to spec 0003. Multi-state
ingest (MD, NJ, PA, OH) defers to spec 0004. The retrieval engine in
v0.1 is a pure-stdlib TF-IDF index that shares the FAISS-shaped on-disk
layout described in spec 0002 design B3; see
`decisions/DEC-002-stdlib-tfidf-engine-for-v0.1.md` for the swap plan.

## how to run

```bash
# v0.1 has no third-party dependencies; pytest is the only dev extra.
pip install -e ".[dev]"

FIXTURE=tests/fixtures/va/PUR-2024-00001

pdr chunk --fixture "$FIXTURE"
pdr index --fixture "$FIXTURE"
pdr index --fixture "$FIXTURE"   # second call prints "no changes"

pdr search \
  --query "data-center cost allocation" \
  --k 5 \
  --index faiss_index/va/PUR-2024-00001

pdr extract \
  --schema cost_allocation_rule \
  --fixture "$FIXTURE"

pytest
```

Outputs land at the spec 0002 paths:
`data/dockets/chunks/va/PUR-2024-00001.jsonl`,
`faiss_index/va/PUR-2024-00001.{faiss,meta.jsonl,index.json}`, and
`data/extracted/va/PUR-2024-00001/cost_allocation_rule.jsonl`.

## layout

v0.1 ships flat modules under `src/pdr/`; the sub-package layout from
the original scaffold (with `ingest/`, `index/`, `extraction/`, `api/`,
`src/pages/`, and `eval/`) lands with spec 0003+ when HTTP, the Astro
page, and the eval suite arrive.

```
puc-docket-rag/
  src/pdr/
    __init__.py
    ingest.py        # fixture loader (pages.jsonl / pages.txt)
    chunk.py         # paragraph chunker + chunk_id normalization
    index.py         # stdlib TF-IDF + idempotency sidecar
    search.py        # top-K search over the v0.1 engine
    extract.py       # FakeAdapter + citation validation
    config.py        # pdr.toml loader
    cli.py           # `pdr` console script
  schemas/
    cost_allocation_rule.schema.json
  scripts/
    voice_lint.py
    validate_schemas.py
  tests/
    test_chunk.py
    test_search.py
    fixtures/va/PUR-2024-00001/
      pages.jsonl
      fixture.meta.json
  data/                  # gitignored output (chunks/, extracted/)
  faiss_index/           # gitignored index payloads
  decisions/
  specs/0001-foundation/
  specs/0002-design/
  AGENTS.md
  LICENSE
  pdr.toml
  pyproject.toml
  README.md
```

## citation faithfulness

The eval suite holds out a hand-labeled set of (question, answer,
expected-citation) tuples. A pipeline pass produces an answer and a
citation. The eval scores:

- **Recall@5**: does the expected citation appear in the top-5 cited
  passages?
- **Citation faithfulness**: does the produced answer's claim appear
  verbatim or as a paraphrase within the cited passage?

The threshold for v0 acceptance is recall@5 >= 90% and faithfulness
>= 95%. Drift below either fails CI.

## license

MIT. See LICENSE.
