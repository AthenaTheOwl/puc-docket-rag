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

import json
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
    from pdr.extract import FakeAdapter, extract, load_schema, validate_citations
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

st.divider()

# --- drive the citation gate yourself ---------------------------------------
# Everything above runs the canned FakeAdapter. This section hands the steering
# wheel to the user: paste your OWN candidate extraction rows (the JSON an LLM
# would emit) and run the repo's real citation gate — pdr.extract.validate_citations —
# against the live retrieved set for the query above. A row survives only if it
# is schema-valid AND its source_citation.chunk_id is a chunk that retrieval
# actually returned. Fabricate a chunk_id, drop a required field, or break the
# line_range pattern and watch the gate reject it, with the reason.
st.subheader("validate your own rules against the citation gate")
st.caption(
    "this is the real engine, not a lookup: your rows go straight into "
    "`pdr.extract.validate_citations(rows, hits, schema)`. a rule is kept only "
    "if it is schema-valid and cites a chunk_id that retrieval returned for the "
    "query above. nothing unsourced gets through."
)

retrieved_ids = [h.chunk_id for h in hits]
if retrieved_ids:
    st.markdown(
        "**chunk_ids in the current retrieved set** (a citation must match one "
        "of these to pass):"
    )
    st.code("\n".join(retrieved_ids), language="text")
else:
    st.info("no passages retrieved for the current query — widen it above first.")

# Pre-fill: one row that cites the top hit (will pass) and one with a
# fabricated all-zeros chunk_id (will be dropped). The user can edit freely.
_top = hits[0] if hits else None
_example = [
    {
        "rule_id": "CAR-101",
        "rule_text": (
            "Data-center load is allocated to the GS-4 rate class."
        ),
        "source_citation": {
            "docket_id": _top.docket_id if _top else doc.docket_id,
            "page_number": _top.page_number if _top else 1,
            "line_range": (
                f"{_top.line_start}-{_top.line_end}" if _top else "1-1"
            ),
            "chunk_id": _top.chunk_id if _top else ("0" * 40),
        },
    },
    {
        "rule_id": "CAR-102",
        "rule_text": (
            "This row cites a chunk retrieval never returned — it must be "
            "dropped, not emitted unsourced."
        ),
        "source_citation": {
            "docket_id": _top.docket_id if _top else doc.docket_id,
            "page_number": 1,
            "line_range": "1-1",
            "chunk_id": "0" * 40,
        },
    },
]

user_json = st.text_area(
    "candidate extraction rows (JSON array)",
    value=json.dumps(_example, indent=2),
    height=320,
    help=(
        "edit the chunk_id, drop a required field, or break the line_range "
        "pattern to see the gate react."
    ),
)

run = st.button("run the citation gate", type="primary")
if run:
    try:
        parsed = json.loads(user_json)
    except json.JSONDecodeError as exc:
        st.error(f"that is not valid JSON: {exc}")
    else:
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            st.error("expected a JSON array of rows (or a single row object).")
        else:
            try:
                schema_doc = load_schema(
                    "cost_allocation_rule", str(SCHEMA_DIR)
                )
                u_kept, u_dropped = validate_citations(
                    parsed, hits, schema=schema_doc
                )
            except Exception as exc:  # pragma: no cover - user-input guard
                st.error(f"the gate could not run on that input: {exc}")
            else:
                c1, c2 = st.columns(2)
                c1.metric("kept (sourced)", len(u_kept))
                c2.metric("dropped", len(u_dropped))
                if u_kept:
                    st.success(
                        f"{len(u_kept)} row(s) passed: schema-valid and citing "
                        "a chunk in the retrieved set."
                    )
                    st.dataframe(
                        [
                            {
                                "rule_id": r.get("rule_id", "<none>"),
                                "chunk_id": r["source_citation"]["chunk_id"][:12],
                                "rule_text": r.get("rule_text", ""),
                            }
                            for r in u_kept
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
                if u_dropped:
                    st.error(
                        f"{len(u_dropped)} row(s) rejected by the gate — and the "
                        "reason for each:"
                    )
                    for r, reason in u_dropped:
                        rid = r.get("rule_id", "<no rule_id>") if isinstance(
                            r, dict
                        ) else "<non-object row>"
                        st.markdown(f"- **{rid}** — {reason}")
                if not u_kept and not u_dropped:
                    st.info("no rows in the input.")

st.divider()
st.caption(
    "v0.1 ships one VA docket fixture (PUR-2024-00001). the pipeline lives in "
    "`src/pdr/`; this page runs the same chunk -> index -> search -> extract "
    "the `pdr demo` verb runs, in a throwaway temp index, and the section above "
    "drives the real `validate_citations` gate on your own rows. "
    "repo: github.com/AthenaTheOwl/puc-docket-rag"
)
