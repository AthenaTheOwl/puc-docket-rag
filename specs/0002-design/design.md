# Design — 0002 Design (v0.1)

v0.1 is four CLI subcommands wired together by a shared on-disk
layout. No HTTP, no frontend. The unit of input is one committed VA
docket fixture (`PUR-2024-00001`); the unit of output is JSON to
stdout or to a JSONL file under `data/`.

## Pipeline

```
tests/fixtures/va/PUR-2024-00001/<doc_id>.pdf  (committed)
              |
          pdr chunk
              v
data/dockets/chunks/va/PUR-2024-00001.jsonl
              |
          pdr index
              v
faiss_index/va/PUR-2024-00001.faiss
faiss_index/va/PUR-2024-00001.meta.jsonl
              |
   +----------+-----------+
   |                      |
pdr search            pdr extract --schema cost_allocation_rule
   |                      |
   v                      v
stdout (json)         data/extracted/va/PUR-2024-00001/cost_allocation_rule.jsonl
```

## Blocks

### B1. Fixture loader (`src/pdr/ingest/fixture.py`)

- Reads one docket directory: a PDF (or a pre-extracted `pages.jsonl`)
  plus `fixture.meta.json`.
- Returns an iterator of `(page_number, page_text)` tuples.
- For PDF input, uses `pypdf` to extract page text; for `pages.jsonl`
  input, reads each row as `{ "page_number": int, "text": str }`.
- Interface: `load_fixture(path) -> FixtureDoc`.

### B2. Chunker (`src/pdr/chunk/paragraph.py`)

- Splits page text on paragraph boundaries; merges short paragraphs
  and splits long ones to land near the 800-token target with 100-token
  overlap. Paragraph boundaries are preserved when the size target
  allows.
- Token count uses `tiktoken` cl100k_base. No model call.
- `line_start` and `line_end` are 1-indexed line numbers in the page's
  extracted text from `page_text.splitlines()`; they refer to the
  source page text, not to the PDF render.
- `chunk_id = sha1(normalized_text + ":" + str(page_number))`.
  Normalization is: Unicode NFC, then collapse runs of whitespace to a
  single space, then strip leading and trailing whitespace.
- Emits chunks with `chunk_id`, `docket_id`, `page_number`,
  `line_start`, `line_end`, `text`.
- Interface: `chunk_pages(pages, cfg) -> Iterator[Chunk]`.

### B3. Indexer (`src/pdr/index/faiss_with_citations.py`)

- Embeds each chunk with the configured sentence-transformers model;
  default `all-MiniLM-L6-v2`. Cache lives under `$HF_HOME` (default
  `~/.cache/huggingface`) or under `[embedding] cache_dir` from
  `pdr.toml`.
- Stores vectors in a FAISS `IndexFlatIP` (cosine via normalized
  vectors).
- Writes `<stem>.meta.jsonl` parallel to `<stem>.faiss`; row N is the
  chunk for FAISS integer ID N and carries `chunk_id`, `docket_id`,
  `page_number`, `line_start`, `line_end`, `text`.
- Idempotency: writes a `<stem>.index.json` sidecar holding
  `{ chunks_sha256, embedding_model_id, config_hash }`. A rebuild
  fires only when any of the three values changes; otherwise the run
  is a no-op and prints `no changes`.
- Interface: `build_index(chunks, out_stem, cfg) -> IndexHandle`.

### B4. Search (`src/pdr/search/cli.py`)

- Loads `<stem>.faiss` plus `<stem>.meta.jsonl`, embeds the query,
  and returns the top-K nearest passages.
- CLI: `pdr search --query "<q>" --k 5 --index <stem>`. `<stem>` is a
  path stem, not a directory: the loader appends `.faiss` and
  `.meta.jsonl` to it.
- Output: a JSON array on stdout, one object per hit, with fields
  `chunk_id`, `docket_id`, `page_number`, `line_start`, `line_end`,
  `text`, `score`.
- Interface: `search(stem, query, k, cfg) -> list[Hit]`.

### B5. Structured extraction (`src/pdr/extraction/cost_allocation_rules.py`)

- Derives the index stem from the fixture path:
  `faiss_index/va/<docket_id>` where `<docket_id>` is read from
  `fixture.meta.json`.
- Retrieves top-K passages for a fixed seed query
  (`cost allocation methodology`) via B4.
- Calls the configured LLM with the passages and the JSON schema; the
  LLM returns a JSON object with a row-level `source_citation` carrying
  `docket_id`, `page_number`, `line_range`, and `chunk_id`.
- Validates the response against
  `schemas/cost_allocation_rule.schema.json` (which spec 0002 extends
  to add the `chunk_id` field to `source_citation`).
- Citation check: `source_citation.chunk_id` must match a `chunk_id`
  returned by B4 in the same call. Rows that fail are dropped and
  logged.
- Interface: `extract(fixture_path, schema, cfg) -> list[dict]`.
- LLM choice is config-driven and sits behind a thin adapter; for
  tests, a `FakeAdapter` returns canned JSON.

## Configuration

`pdr.toml` at repo root with sections for `chunk`, `index`,
`embedding`, `extraction`. CLI flags override file values. Defaults
ship in `src/pdr/config.py`. `[embedding]` carries `model_id` and
`cache_dir`; the indexer hashes the resolved `chunk` + `index`
sections into `config_hash` for the idempotency sidecar.

## Failure modes per block

| Block | Failure | Behavior |
|---|---|---|
| B1 | Missing `fixture.meta.json` | Exit non-zero, print the missing field |
| B1 | PDF page extraction returns empty text | Skip page, log to stderr |
| B2 | Paragraph longer than 4x target | Force-split on sentence boundary, log |
| B2 | Tokenizer init fails | Exit non-zero |
| B3 | Embedding model download blocked | Exit non-zero with model id and cache path |
| B3 | FAISS write fails (disk full) | Exit non-zero; partial files removed |
| B4 | Index stem files missing | Exit non-zero with the expected `.faiss` path |
| B4 | Query embedding NaN | Exit non-zero |
| B5 | LLM JSON does not parse | Drop row, log to stderr |
| B5 | `source_citation.chunk_id` not in retrieved set | Drop row, log |
| B5 | LLM call exceeds timeout | Drop row, log; retry once with backoff |

## On-disk layout

Index artifacts share a single path stem so the CLI can take `--index
<stem>` and append the file suffix it needs.

```
tests/fixtures/va/PUR-2024-00001/
  <doc_id>.pdf            (or pages.jsonl)
  fixture.meta.json
data/dockets/chunks/va/PUR-2024-00001.jsonl              (gitignored)
faiss_index/va/PUR-2024-00001.faiss                      (gitignored)
faiss_index/va/PUR-2024-00001.meta.jsonl                 (gitignored)
faiss_index/va/PUR-2024-00001.index.json                 (gitignored)
data/extracted/va/PUR-2024-00001/cost_allocation_rule.jsonl  (gitignored)
```

## Out of scope for v0.1

- HTTP server, FastAPI, or any network listener.
- The Astro page at `src/pages/search.astro`.
- `load_forecast` extraction.
- Citation-faithfulness eval suite and CI gate.
- Multi-state ingest (MD, NJ, PA, OH) and live PUC website crawling.
- LLM-graded faithfulness; v0.1 only checks that citations resolve to
  real chunks, not that the text supports the claim.
- Re-ranking, hybrid BM25 + vector, cross-encoder rerankers.
- Authentication, rate limits, request logging.
