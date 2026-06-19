# Design — 0001 Foundation

## Architecture sketch

Six stages, each a separate CLI subcommand, each with on-disk caches.

```
state PUC website
       |
   pdr ingest
       v
data/dockets/raw/VA/<docket_id>/<doc_id>.pdf
       |
   pdr chunk
       v
data/dockets/chunks/VA/<docket_id>.jsonl
       |
   pdr index
       v
faiss_index/VA.faiss + faiss_index/VA.meta.jsonl
       |
   pdr extract
       v
data/extracted/VA/<schema>.jsonl
       |
   pdr serve
       v
  FastAPI on :8000
       |
       v
  src/pages/search.astro (frontend)
```

## Chunking

Documents are split with paragraph boundaries respected. Each chunk
carries `docket_id`, `page_number`, `line_start`, `line_end` so the
search response can render an exact citation. Chunk size targets 800
tokens with 100-token overlap.

## Index

FAISS with cosine similarity over chunk embeddings. The
`faiss_with_citations.py` wrapper layers citation metadata on top of
FAISS's integer IDs by maintaining a parallel `meta.jsonl` keyed by
the FAISS ID.

## Structured extraction

`cost_allocation_rules.py` and `load_forecasts.py` each define:

1. A retrieval query.
2. A prompt that takes top-K passages and emits a JSON object matching
   the corresponding schema.
3. A post-extraction validator that confirms every field in the JSON
   has a citation reference to one of the supplied passages.

Outputs that fail post-extraction validation are dropped, not
patched.

## API

`POST /search` body: `{ "query": str, "k": int (default 5),
"states": list[str] (default ["VA"]) }`.

Response: `{ "passages": [{ "text": str, "docket_id": str,
"page": int, "line_start": int, "line_end": int, "score": float
}] }`.

## Citation-faithfulness eval

The eval suite at `eval/citation_faithfulness.py`:

1. Loads `eval/fixtures/*.jsonl`, each line a `(query, expected_claim,
   expected_docket_id, expected_page_range)` tuple.
2. For each, calls `POST /search` and records the top-5.
3. Recall@5: did the expected `(docket_id, page_range)` appear?
4. Faithfulness: for the top-1 passage cited as supporting
   `expected_claim`, does the passage contain the claim? Scored
   manually for v0; LLM-graded with human spot-check later.

The gate fails the build below recall@5 90% or faithfulness 95%.

## Voice

Search responses are passages with citations. No editorializing prose.
The Astro page renders results plainly.
