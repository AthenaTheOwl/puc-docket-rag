"""Stdlib TF-IDF index over a FAISS-shaped on-disk layout.

v0.1 ships a pure-stdlib retrieval engine so the vertical slice runs
without network access or wheels. The path layout — three siblings
sharing a stem (``<stem>.faiss``, ``<stem>.meta.jsonl``,
``<stem>.index.json``) — matches design B3 and lets the engine swap to
FAISS + ``sentence-transformers`` in spec 0003 without changing any CLI
flag, meta-row field, or idempotency-sidecar key. The ``.faiss`` file
holds a JSON-encoded TF-IDF payload in v0.1; see DEC-002 for the
engine-swap rationale and the binary FAISS migration plan.

The idempotency sidecar carries ``chunks_sha256`` (over the chunk rows
fed to the index), ``embedding_model_id`` (the engine identifier), and
``config_hash`` (a SHA-256 of the resolved ``[chunk]`` + ``[index]``
sections from ``pdr.toml``).  A rebuild only fires when one of the
three changes.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

EMBEDDING_MODEL_ID = "stdlib-tfidf-v1"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class IndexHandle:
    stem: Path
    embedding_model_id: str
    vocab: dict[str, int]
    idf: list[float]
    doc_vectors: list[dict[int, float]]
    meta_rows: list[dict]
    chunks_sha256: str
    config_hash: str
    written: bool = True
    note: str = ""


@dataclass(frozen=True)
class IndexConfig:
    """Resolved chunk + index configuration the sidecar hashes.

    Mirrors the ``[chunk]`` and ``[index]`` sections of ``pdr.toml`` so a
    config edit in either section invalidates the idempotency key. Keep
    this in lockstep with ``pdr.config.load_config``.
    """

    target_tokens: int = 800
    overlap_tokens: int = 100
    min_df: int = 1
    embedding_model_id: str = EMBEDDING_MODEL_ID

    def hash(self) -> str:
        payload = json.dumps(
            {
                "chunk": {
                    "target_tokens": self.target_tokens,
                    "overlap_tokens": self.overlap_tokens,
                },
                "index": {
                    "min_df": self.min_df,
                    "embedding_model_id": self.embedding_model_id,
                },
            },
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _chunks_sha256(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update(row["chunk_id"].encode("utf-8"))
        h.update(b"\x1f")
        h.update(row["text"].encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()


def _read_sidecar(sidecar: Path) -> dict | None:
    if not sidecar.is_file():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def build_index(
    chunks: Iterable[dict],
    out_stem: str | Path,
    *,
    config: IndexConfig | None = None,
) -> IndexHandle:
    """Build a TF-IDF index from chunk dicts. Idempotent: if the
    sidecar's three keys are unchanged, skip the rebuild and return a
    handle with ``written=False, note='no changes'``.
    """
    cfg = config or IndexConfig()
    stem = Path(out_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "chunk_id": c["chunk_id"],
            "docket_id": c["docket_id"],
            "page_number": c["page_number"],
            "line_start": c["line_start"],
            "line_end": c["line_end"],
            "text": c["text"],
        }
        for c in chunks
    ]
    if not rows:
        raise ValueError("build_index: no chunks given")

    chunks_hash = _chunks_sha256(rows)
    cfg_hash = cfg.hash()
    model_id = cfg.embedding_model_id

    sidecar_path = stem.with_suffix(".index.json")
    existing = _read_sidecar(sidecar_path)
    if (
        existing
        and existing.get("chunks_sha256") == chunks_hash
        and existing.get("embedding_model_id") == model_id
        and existing.get("config_hash") == cfg_hash
        and stem.with_suffix(".faiss").is_file()
        and stem.with_suffix(".meta.jsonl").is_file()
    ):
        vocab, idf, doc_vectors = _load_vectors(stem)
        meta_rows = _load_meta(stem)
        return IndexHandle(
            stem=stem,
            embedding_model_id=model_id,
            vocab=vocab,
            idf=idf,
            doc_vectors=doc_vectors,
            meta_rows=meta_rows,
            chunks_sha256=chunks_hash,
            config_hash=cfg_hash,
            written=False,
            note="no changes",
        )

    df: Counter[str] = Counter()
    tokenized: list[list[str]] = []
    for row in rows:
        toks = _tokenize(row["text"])
        tokenized.append(toks)
        for t in set(toks):
            df[t] += 1

    vocab_terms = sorted(t for t, n in df.items() if n >= cfg.min_df)
    vocab = {t: i for i, t in enumerate(vocab_terms)}
    n_docs = len(rows)
    idf = [
        math.log((1 + n_docs) / (1 + df[t])) + 1.0 for t in vocab_terms
    ]

    doc_vectors: list[dict[int, float]] = []
    for toks in tokenized:
        tf = Counter(toks)
        vec: dict[int, float] = {}
        for term, count in tf.items():
            ti = vocab.get(term)
            if ti is None:
                continue
            vec[ti] = count * idf[ti]
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm > 0:
            for k in list(vec.keys()):
                vec[k] /= norm
        doc_vectors.append(vec)

    _write_meta(stem, rows)
    _write_vectors(stem, vocab_terms, idf, doc_vectors, model_id)
    sidecar_path.write_text(
        json.dumps(
            {
                "chunks_sha256": chunks_hash,
                "embedding_model_id": model_id,
                "config_hash": cfg_hash,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return IndexHandle(
        stem=stem,
        embedding_model_id=model_id,
        vocab=vocab,
        idf=idf,
        doc_vectors=doc_vectors,
        meta_rows=rows,
        chunks_sha256=chunks_hash,
        config_hash=cfg_hash,
        written=True,
        note="built",
    )


def load_index(stem: str | Path) -> IndexHandle:
    stem_p = Path(stem)
    sidecar = _read_sidecar(stem_p.with_suffix(".index.json"))
    if sidecar is None:
        raise FileNotFoundError(
            f"missing index sidecar at {stem_p.with_suffix('.index.json')}"
        )
    if not stem_p.with_suffix(".faiss").is_file():
        raise FileNotFoundError(
            f"missing index file at {stem_p.with_suffix('.faiss')}"
        )
    vocab, idf, doc_vectors = _load_vectors(stem_p)
    meta_rows = _load_meta(stem_p)
    return IndexHandle(
        stem=stem_p,
        embedding_model_id=sidecar["embedding_model_id"],
        vocab=vocab,
        idf=idf,
        doc_vectors=doc_vectors,
        meta_rows=meta_rows,
        chunks_sha256=sidecar["chunks_sha256"],
        config_hash=sidecar["config_hash"],
        written=False,
        note="loaded",
    )


def _write_meta(stem: Path, rows: list[dict]) -> None:
    path = stem.with_suffix(".meta.jsonl")
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_meta(stem: Path) -> list[dict]:
    path = stem.with_suffix(".meta.jsonl")
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_vectors(
    stem: Path,
    vocab_terms: list[str],
    idf: list[float],
    doc_vectors: list[dict[int, float]],
    model_id: str,
) -> None:
    payload = {
        "embedding_model_id": model_id,
        "vocab": vocab_terms,
        "idf": idf,
        "doc_vectors": [
            {str(k): v for k, v in vec.items()} for vec in doc_vectors
        ],
    }
    stem.with_suffix(".faiss").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _load_vectors(
    stem: Path,
) -> tuple[dict[str, int], list[float], list[dict[int, float]]]:
    data = json.loads(stem.with_suffix(".faiss").read_text(encoding="utf-8"))
    vocab_terms = data["vocab"]
    vocab = {t: i for i, t in enumerate(vocab_terms)}
    idf = list(data["idf"])
    doc_vectors = [
        {int(k): float(v) for k, v in vec.items()} for vec in data["doc_vectors"]
    ]
    return vocab, idf, doc_vectors
