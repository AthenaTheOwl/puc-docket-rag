# AGENTS.md — puc-docket-rag

Operating contract for AI agents working in this repo.

## What this repo is

A citation-faithful RAG index over public PUC and FERC filings.
Downstream consumers are RatepayerExposure (assumption sourcing) and
SiteAtlas (evidence layer). The repo's discipline is that every answer
cites a page and line of a real docket and the citation is verified to
contain the claim.

## Roles you may see in tasks

| Role | What they do |
|---|---|
| `ingester` | Pulls dockets from state PUC websites; caches raw |
| `chunker` | Splits documents into citation-anchored chunks |
| `indexer` | Embeds chunks; maintains the FAISS index |
| `extractor` | Runs structured passes (cost allocation, load forecast) |
| `faithfulness-evaluator` | Maintains the eval suite and the threshold gate |

Not all roles are implemented in v0.

## Voice constraints

- No marketing words. No "leverage", "synergy", "best-in-class",
  "seamless", "cutting-edge".
- No antithetical reversals as a structural device.
- The search API and the page return short paragraphs with explicit
  citations. No essay output. No editorializing.

## Gates (will land in spec 0002)

```bash
uv run pytest
python scripts/voice_lint.py src/pages/ docs/
python scripts/validate_schemas.py
uv run pdr eval citation-faithfulness  # threshold gate
```

A drop below recall@5 90% or faithfulness 95% fails the gate.

## Out of scope

- States outside PJM for v0. Other ISOs land later if demand pulls.
- Document classification beyond the two structured schemas.
- Summarization output. The index returns passages with citations,
  not summaries.
- Hosting the search publicly. The Astro page is for local /
  development use; production hosting is a separate concern.
