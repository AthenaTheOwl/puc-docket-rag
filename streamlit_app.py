"""puc-docket-rag — live demo (Streamlit Community Cloud).

Mirrors the no-arg `pdr demo` verb as an interactive page. Runs the full
v0.1 pipeline (chunk -> index -> search -> citation-gated extract) over the
committed VA docket fixture (tests/fixtures/va/PUR-2024-00001), entirely
offline and read-only. The index is built in a throwaway temp dir; nothing
is written to the repo tree. No network, no secrets.

The headline finding: every extracted cost-allocation rule carries a
page-and-line citation back to the docket, and a rule whose citation is
not in the retrieved set is dropped, never emitted unsourced.

Deploy: Streamlit Community Cloud -> New app -> repo AthenaTheOwl/puc-docket-rag,
branch main, main file streamlit_app.py.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import streamlit as st

# Resolve paths relative to this file so the app runs from any cwd, and put
# the local package on the path so `import pdr` works whether or not the
# package was pip-installed (Streamlit Cloud installs it via `.` in
# requirements.txt; locally it may already be editable-installed).
REPO = Path(__file__).resolve().parent
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURE = REPO / "tests" / "fixtures" / "va" / "PUR-2024-00001"
SCHEMA_DIR = REPO / "schemas"
DEFAULT_QUERY = "data-center cost allocation methodology"

st.set_page_config(
    page_title="puc-docket-rag — citation-faithful docket retrieval",
    layout="wide",
)
st.title("puc-docket-rag")
st.caption(
    "citation-faithful retrieval over a state-PUC docket: every extracted "
    "cost-allocation rule cites the docket page and line, and an unsourced "
    "rule is dropped rather than emitted."
)

# --- guard: committed fixture must be present -------------------------------
if not (FIXTURE / "pages.jsonl").is_file() or not (
    FIXTURE / "fixture.meta.json"
).is_file():
    st.warning(
        "missing committed fixture under tests/fixtures/va/PUR-2024-00001 "
        "(pages.jsonl + fixture.meta.json)."
    )
    st.stop()

try:
    from pdr.chunk import chunk_pages
    from pdr.config import Config
    from pdr.extract import FakeAdapter, extract
    from pdr.index import IndexConfig, build_index
    from pdr.ingest import load_fixture
    from pdr.search import search
except Exception as exc:  # pragma: no cover - import guard for cloud
    st.warning(f"could not import the pdr package: {exc}")
    st.stop()


@st.cache_resource(show_spinner=False)
def _load_doc_and_chunks():
    cfg = Config()
    doc = load_fixture(FIXTURE)
    chunks = [
        c.to_jsonable()
        for c in chunk_pages(
            doc.pages(),
            docket_id=doc.docket_id,
            target_tokens=cfg.chunk.target_tokens,
            overlap_tokens=cfg.chunk.overlap_tokens,
        )
    ]
    return cfg, doc, chunks


@st.cache_resource(show_spinner=False)
def _build_index_stem():
    """Build the TF-IDF index once into a persistent temp dir and return the
    path stem. Cached for the session so the slider/query rerun is instant.
    """
    cfg, doc, chunks = _load_doc_and_chunks()
    tmp = tempfile.mkdtemp(prefix="pdr-streamlit-")
    stem = Path(tmp) / "va" / doc.docket_id
    index_cfg = IndexConfig(
        target_tokens=cfg.chunk.target_tokens,
        overlap_tokens=cfg.chunk.overlap_tokens,
        min_df=cfg.index.min_df,
        embedding_model_id=cfg.index.embedding_model_id,
    )
    build_index(chunks, stem, config=index_cfg)
    return str(stem)


try:
    cfg, doc, chunks = _load_doc_and_chunks()
    stem = _build_index_stem()
except Exception as exc:
    st.warning(f"failed to build the demo index: {exc}")
    st.stop()

# --- docket header ----------------------------------------------------------
st.subheader(f"docket {doc.docket_id}  ({doc.meta.get('state', 'VA')})")

# --- interactive controls ---------------------------------------------------
left, right = st.columns([3, 1])
query = left.text_input(
    "retrieval query",
    value=DEFAULT_QUERY,
    help="TF-IDF query against the committed docket's chunks.",
)
k = right.slider("top-K passages", min_value=1, max_value=len(chunks) or 1,
                 value=min(3, len(chunks) or 1))

hits = search(stem, query, k=k)
kept, dropped = extract(
    stem,
    "cost_allocation_rule",
    adapter=FakeAdapter(),
    query=query,
    k=max(k, 3),
    schema_dir=str(SCHEMA_DIR),
)

# --- summary metrics --------------------------------------------------------
m1, m2, m3 = st.columns(3)
m1.metric("chunks indexed", len(chunks))
m2.metric("rules kept", len(kept), help="citation matched a retrieved chunk")
m3.metric("rules dropped", len(dropped), help="citation not in the retrieved set")

# --- key finding ------------------------------------------------------------
if kept:
    row = kept[0]
    sc = row["source_citation"]
    st.success(
        f"**citation gate held.** kept rule {row['rule_id']} cites "
        f"{sc['docket_id']} p.{sc['page_number']} L{sc['line_range']} — a "
        f"chunk that is in the retrieved set. "
        + (
            f"{len(dropped)} row(s) carrying a fabricated chunk_id were "
            "dropped rather than emitted unsourced."
            if dropped
            else "no unsourced rows were emitted."
        )
    )
elif dropped:
    st.info(
        "every candidate rule failed the citation gate and was dropped — "
        "nothing unsourced was emitted."
    )
else:
    st.info("no rules extracted for this query.")

# --- ranked passages --------------------------------------------------------
st.markdown("#### top passages by TF-IDF relevance")
if not hits:
    st.info("no matching passages for this query — try different terms.")
else:
    st.dataframe(
        [
            {
                "rank": i,
                "score": round(h.score, 3),
                "citation": f"p.{h.page_number} L{h.line_start}-{h.line_end}",
                "chunk_id": h.chunk_id[:12],
                "passage": " ".join(h.text.split())[:200],
            }
            for i, h in enumerate(hits, start=1)
        ],
        use_container_width=True,
        hide_index=True,
    )

# --- extraction detail ------------------------------------------------------
st.markdown("#### extracted cost-allocation rules (citation-gated)")
if kept:
    st.dataframe(
        [
            {
                "rule_id": r["rule_id"],
                "citation": (
                    f"{r['source_citation']['docket_id']} "
                    f"p.{r['source_citation']['page_number']} "
                    f"L{r['source_citation']['line_range']}"
                ),
                "rule_text": r["rule_text"],
            }
            for r in kept
        ],
        use_container_width=True,
        hide_index=True,
    )
if dropped:
    with st.expander(f"dropped rows ({len(dropped)}) — why each was rejected"):
        for r, reason in dropped:
            rid = r.get("rule_id", "<no rule_id>")
            st.markdown(f"- **{rid}** — {reason}")

st.caption(
    "v0.1 ships one VA docket fixture (PUR-2024-00001). the pipeline lives in "
    "`src/pdr/`; this page runs the same chunk -> index -> search -> extract "
    "the `pdr demo` verb runs, in a throwaway temp index. "
    "repo: github.com/AthenaTheOwl/puc-docket-rag"
)
