"""No-arg ``pdr demo``: run the full v0.1 pipeline over the committed VA
fixture and print a human-readable result.

The demo is read-only and offline. It loads the committed fixture
(``tests/fixtures/va/PUR-2024-00001``), chunks it, builds the stdlib
TF-IDF index in a throwaway temp directory, runs a default retrieval
query, and runs the ``cost_allocation_rule`` extraction with citation
validation. It then renders:

- the docket header (id, state, source),
- the top retrieval hits as a ranked table with page/line citations,
- the citation-validated extraction: rules kept vs. rows dropped, so the
  citation gate (a row whose chunk_id is not in the retrieved set is
  dropped, never patched) is visible.

Nothing is written to the repo tree; the index lives in a ``TemporaryDirectory``
that is removed on exit.
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

from pdr.chunk import chunk_pages
from pdr.config import Config
from pdr.extract import FakeAdapter, extract
from pdr.index import IndexConfig, build_index
from pdr.ingest import load_fixture
from pdr.search import Hit, search

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "va" / "PUR-2024-00001"
DEFAULT_QUERY = "data-center cost allocation methodology"
DEFAULT_K = 3


def _truncate(text: str, width: int = 88) -> str:
    snippet = " ".join(text.split())
    if len(snippet) <= width:
        return snippet
    return snippet[: width - 3].rstrip() + "..."


def render_demo(
    fixture: Path | str = DEFAULT_FIXTURE,
    *,
    query: str = DEFAULT_QUERY,
    k: int = DEFAULT_K,
    cfg: Config | None = None,
) -> str:
    """Run the pipeline and return the rendered report as a string."""
    cfg = cfg or Config()
    doc = load_fixture(fixture)
    chunks = [
        c.to_jsonable()
        for c in chunk_pages(
            doc.pages(),
            docket_id=doc.docket_id,
            target_tokens=cfg.chunk.target_tokens,
            overlap_tokens=cfg.chunk.overlap_tokens,
        )
    ]

    lines: list[str] = []
    lines.append("puc-docket-rag demo -- citation-faithful docket retrieval")
    lines.append("=" * 64)
    lines.append(f"docket    {doc.docket_id}  ({doc.meta.get('state', '?')})")
    lines.append(f"source    {doc.meta.get('source_url', '?')}")
    lines.append(f"pages     {len(chunks)} chunk(s) indexed")
    lines.append(f"query     {query!r}")
    lines.append("")

    with tempfile.TemporaryDirectory(prefix="pdr-demo-") as tmp:
        stem = Path(tmp) / "va" / doc.docket_id
        index_cfg = IndexConfig(
            target_tokens=cfg.chunk.target_tokens,
            overlap_tokens=cfg.chunk.overlap_tokens,
            min_df=cfg.index.min_df,
            embedding_model_id=cfg.index.embedding_model_id,
        )
        build_index(chunks, stem, config=index_cfg)
        hits: list[Hit] = search(stem, query, k=k)

        lines.append(f"top {len(hits)} passages by TF-IDF relevance")
        lines.append("-" * 64)
        if not hits:
            lines.append("  (no matching passages)")
        for rank, h in enumerate(hits, start=1):
            cite = f"p.{h.page_number} L{h.line_start}-{h.line_end}"
            lines.append(f"  {rank}. score {h.score:.3f}  [{cite}]  {h.chunk_id[:12]}")
            for wrapped in textwrap.wrap(_truncate(h.text, 200), width=72):
                lines.append(f"       {wrapped}")
        lines.append("")

        kept, dropped = extract(
            stem,
            "cost_allocation_rule",
            adapter=FakeAdapter(),
            query=query,
            k=DEFAULT_K if k < DEFAULT_K else k,
            schema_dir=cfg.extraction.schema_dir,
        )

    lines.append("extracted cost-allocation rules (citation-gated)")
    lines.append("-" * 64)
    lines.append(f"  kept {len(kept)}   dropped {len(dropped)}")
    for row in kept:
        sc = row["source_citation"]
        cite = f"{sc['docket_id']} p.{sc['page_number']} L{sc['line_range']}"
        lines.append(f"  KEPT  {row['rule_id']}  [{cite}]")
        for wrapped in textwrap.wrap(row["rule_text"], width=68):
            lines.append(f"        {wrapped}")
    for row, reason in dropped:
        rid = row.get("rule_id", "<no rule_id>")
        lines.append(f"  DROP  {rid}  ({reason})")
    lines.append("")
    lines.append(
        "the dropped row carried a fabricated chunk_id; the citation gate "
        "removed it"
    )
    lines.append("rather than emit an unsourced rule.")
    return "\n".join(lines)


def run_demo() -> int:
    print(render_demo())
    return 0
