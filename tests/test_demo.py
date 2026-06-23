"""Tests for the no-arg ``pdr demo`` command.

The demo runs the full pipeline (chunk -> index -> search -> extract)
over the committed VA fixture in a throwaway temp dir and renders a
human-readable report. These tests assert it runs with no args, exits 0,
writes nothing to the repo tree, and surfaces the kept rule and the
citation-gated drop.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdr.cli import main
from pdr.demo import render_demo


def test_render_demo_surfaces_docket_hits_and_extraction():
    report = render_demo()
    assert "PUR-2024-00001" in report
    assert "top 3 passages by TF-IDF relevance" in report
    # the kept, sourced rule and the dropped fabricated-citation row
    assert "KEPT  CAR-001" in report
    assert "DROP  CAR-002" in report
    assert "not in retrieved set" in report
    # a real page/line citation appears
    assert "p.1 L1-23" in report


def test_demo_cli_runs_with_no_args_exit_zero(capsys):
    rc = main(["demo"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "citation-faithful docket retrieval" in out


def test_demo_writes_nothing_to_repo_tree():
    before = {p for p in (ROOT / "data").rglob("*")} if (ROOT / "data").exists() else set()
    faiss_before = {
        p for p in (ROOT / "faiss_index").rglob("*")
    } if (ROOT / "faiss_index").exists() else set()
    render_demo()
    after = {p for p in (ROOT / "data").rglob("*")} if (ROOT / "data").exists() else set()
    faiss_after = {
        p for p in (ROOT / "faiss_index").rglob("*")
    } if (ROOT / "faiss_index").exists() else set()
    assert before == after, "demo must not write under data/"
    assert faiss_before == faiss_after, "demo must not write under faiss_index/"
