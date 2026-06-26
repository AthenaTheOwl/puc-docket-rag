# puc-docket-rag

Two cost-allocation rules come out of the docket. One cites page 1, line 1-23. The
other cites a chunk_id of forty zeros that exists nowhere in the filing. The second
one gets dropped. That dropped row is the whole point.

## What it does

Regulatory dockets are where the cost of the buildout gets assigned to somebody's
bill, and the rule that does the assigning is buried in a PDF on a state commission's
website, on a page, on a line. puc-docket-rag indexes those filings full-text and
pulls the structured rules out — cost-allocation methods, load forecasts — with a
page-and-line citation hanging off every one.

The citation is not decoration; it is the gate. Every extracted rule has to point at
a passage that retrieval actually returned. A rule whose citation isn't in the
retrieved set is dropped, never emitted unsourced. The eval suite measures that
faithfulness and the build fails below threshold, so an answer that can't show its
work doesn't ship. The extraction pattern is borrowed from
[supplier-risk-rag-agent](https://github.com/AthenaTheOwl/supplier-risk-rag-agent);
the rest is deliberately thin — ingest, chunk, embed, search, two extraction passes.

v0.1 ships the vertical slice over one Virginia docket fixture (`PUR-2024-00001`):
chunk, index, search, and `cost_allocation_rule` extraction with the citation gate
wired in. The HTTP API, the Astro search page, and `load_forecast` extraction defer
to spec 0003; the other PJM states (MD, NJ, PA, OH) defer to spec 0004. The retrieval
engine is a pure-stdlib TF-IDF index sitting in the FAISS-shaped on-disk layout, so
the swap to FAISS later is a body transplant, not a rewrite — see
`decisions/DEC-002-stdlib-tfidf-engine-for-v0.1.md`.

## Try it

One no-arg command runs the whole v0.1 pipeline (chunk, index, search, extract) over
the committed VA fixture and prints a readable result. It is offline and read-only;
the index is built in a temp dir, nothing is written to the repo tree.

```bash
pdr demo
```

```
docket    PUR-2024-00001  (VA)
query     'data-center cost allocation methodology'

top 3 passages by TF-IDF relevance
  1. score 0.259  [p.1 L1-23]  b5d04a590b08
       ... Re: Cost Allocation Methodology for Large Customer Loads ...

extracted cost-allocation rules (citation-gated)
  kept 1   dropped 1
  KEPT  CAR-001  [PUR-2024-00001 p.1 L1-23]
        Data-center load is allocated to the GS-4 rate class.
  DROP  CAR-002  (chunk_id '0000...0000' not in retrieved set)
```

Every kept rule carries a page-and-line citation back to the docket. The dropped one
named a chunk that retrieval never surfaced, so the gate removed it rather than let
an unsourced rule through.

## Live demo

An interactive Streamlit page wraps the same `pdr demo` result: the ranked TF-IDF
passages with page/line citations and the citation-gated extraction (kept vs
dropped). It runs offline over the committed VA fixture — no network, no secrets.

<!-- live url: https://<your-app>.streamlit.app (fill in after deploy) -->

local:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

streamlit community cloud: new app -> repo `AthenaTheOwl/puc-docket-rag`,
branch `main`, main file `streamlit_app.py`.

## How it connects

puc-docket-rag is the evidence layer the energy-line repos read from — the place
where a claim about who pays gets a docket page behind it:

- [ratepayer-exposure](https://github.com/AthenaTheOwl/ratepayer-exposure) — turns
  these cost-allocation rules into the number on one household's power bill.
- [site-atlas](https://github.com/AthenaTheOwl/site-atlas) — the civic-data front end
  that points at the same dockets from the queue side.
- [supplier-risk-rag-agent](https://github.com/AthenaTheOwl/supplier-risk-rag-agent)
  — the citation-faithful extraction pattern this repo borrows wholesale.

## How to run

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

## Layout

v0.1 ships flat modules under `src/pdr/`; the sub-package layout from the original
scaffold (with `ingest/`, `index/`, `extraction/`, `api/`, `src/pages/`, and `eval/`)
lands with spec 0003+ when HTTP, the Astro page, and the eval suite arrive.

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

## Citation faithfulness

The eval suite holds out a hand-labeled set of (question, answer, expected-citation)
tuples. A pipeline pass produces an answer and a citation, and the eval scores two
things:

- **Recall@5**: does the expected citation appear in the top-5 cited passages?
- **Citation faithfulness**: does the produced answer's claim appear verbatim or as a
  paraphrase within the cited passage?

The threshold for v0 acceptance is recall@5 >= 90% and faithfulness >= 95%. Drift
below either fails CI.

## License

MIT. See LICENSE.
