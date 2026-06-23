"""``pdr`` CLI dispatcher."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pdr.chunk import chunk_pages
from pdr.config import Config, load_config
from pdr.demo import render_demo
from pdr.extract import FakeAdapter, extract, write_jsonl
from pdr.index import IndexConfig, build_index
from pdr.ingest import load_fixture
from pdr.search import search


DEFAULT_STATE = "va"
DEFAULT_CHUNK_OUT = Path("data/dockets/chunks") / DEFAULT_STATE
DEFAULT_INDEX_OUT = Path("faiss_index") / DEFAULT_STATE
DEFAULT_EXTRACT_OUT = Path("data/extracted") / DEFAULT_STATE


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fixture",
        type=Path,
        required=True,
        help="path to a fixture directory (with pages.jsonl + fixture.meta.json) "
        "or to a pages.jsonl/pages.txt file",
    )


def _cmd_chunk(args: argparse.Namespace, cfg: Config) -> int:
    doc = load_fixture(args.fixture)
    target = args.target_tokens or cfg.chunk.target_tokens
    overlap = args.overlap_tokens or cfg.chunk.overlap_tokens
    chunks = list(
        chunk_pages(
            doc.pages(),
            docket_id=doc.docket_id,
            target_tokens=target,
            overlap_tokens=overlap,
        )
    )
    out_dir = args.out or DEFAULT_CHUNK_OUT
    out_path = out_dir / f"{doc.docket_id}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_jsonable(), ensure_ascii=False) + "\n")
    print(json.dumps({"wrote": str(out_path), "chunks": len(chunks)}))
    return 0


def _cmd_index(args: argparse.Namespace, cfg: Config) -> int:
    doc = load_fixture(args.fixture)
    target = args.target_tokens or cfg.chunk.target_tokens
    overlap = args.overlap_tokens or cfg.chunk.overlap_tokens
    chunks = list(
        chunk_pages(
            doc.pages(),
            docket_id=doc.docket_id,
            target_tokens=target,
            overlap_tokens=overlap,
        )
    )
    rows = [c.to_jsonable() for c in chunks]
    out_stem = (args.out or DEFAULT_INDEX_OUT) / doc.docket_id
    index_cfg = IndexConfig(
        target_tokens=target,
        overlap_tokens=overlap,
        min_df=cfg.index.min_df,
        embedding_model_id=cfg.index.embedding_model_id,
    )
    handle = build_index(rows, out_stem, config=index_cfg)
    if not handle.written:
        print("no changes")
    else:
        print(
            json.dumps(
                {
                    "stem": str(out_stem),
                    "chunks": len(rows),
                    "model": handle.embedding_model_id,
                }
            )
        )
    return 0


def _cmd_search(args: argparse.Namespace, cfg: Config) -> int:
    del cfg
    hits = search(args.index, args.query, k=args.k)
    print(json.dumps([h.to_jsonable() for h in hits], ensure_ascii=False))
    return 0


def _cmd_extract(args: argparse.Namespace, cfg: Config) -> int:
    doc = load_fixture(args.fixture)
    stem = (args.index_dir or DEFAULT_INDEX_OUT) / doc.docket_id
    query = args.query or cfg.extraction.default_query
    k = args.k or cfg.extraction.default_k
    kept, dropped = extract(
        stem,
        args.schema,
        adapter=FakeAdapter(),
        query=query,
        k=k,
        schema_dir=cfg.extraction.schema_dir,
    )
    out_path = (args.out or DEFAULT_EXTRACT_OUT) / doc.docket_id / f"{args.schema}.jsonl"
    write_jsonl(kept, out_path)
    print(
        json.dumps(
            {
                "wrote": str(out_path),
                "kept": len(kept),
                "dropped": len(dropped),
            }
        )
    )
    return 0


def _cmd_demo(args: argparse.Namespace, cfg: Config) -> int:
    print(render_demo(cfg=cfg))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pdr", description="puc-docket-rag v0.1 CLI")
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to pdr.toml (defaults to ./pdr.toml)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser(
        "demo",
        help="run the full pipeline over the committed VA fixture and print "
        "a readable result (no args, offline, read-only)",
    )
    demo.set_defaults(func=_cmd_demo)

    chunk = sub.add_parser("chunk", help="paragraph-chunk a fixture to JSONL")
    _add_common(chunk)
    chunk.add_argument("--out", type=Path)
    chunk.add_argument("--target-tokens", type=int, default=None)
    chunk.add_argument("--overlap-tokens", type=int, default=None)
    chunk.set_defaults(func=_cmd_chunk)

    idx = sub.add_parser("index", help="build the v0.1 TF-IDF index from a fixture")
    _add_common(idx)
    idx.add_argument("--out", type=Path)
    idx.add_argument("--target-tokens", type=int, default=None)
    idx.add_argument("--overlap-tokens", type=int, default=None)
    idx.set_defaults(func=_cmd_index)

    sr = sub.add_parser("search", help="top-K search against an index stem")
    sr.add_argument("--query", required=True)
    sr.add_argument("--k", type=int, default=5)
    sr.add_argument("--index", required=True, help="path stem (no suffix)")
    sr.set_defaults(func=_cmd_search)

    ex = sub.add_parser("extract", help="structured extraction with citation check")
    _add_common(ex)
    ex.add_argument("--schema", required=True, choices=["cost_allocation_rule"])
    ex.add_argument("--index-dir", type=Path)
    ex.add_argument("--out", type=Path)
    ex.add_argument("--query", default=None)
    ex.add_argument("--k", type=int, default=None)
    ex.set_defaults(func=_cmd_extract)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    return args.func(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
