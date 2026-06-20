"""Top-K search over a TF-IDF index built by `pdr.index`."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from pdr.index import IndexHandle, _tokenize, load_index


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    docket_id: str
    page_number: int
    line_start: int
    line_end: int
    text: str
    score: float

    def to_jsonable(self) -> dict:
        return asdict(self)


def _query_vector(query: str, handle: IndexHandle) -> dict[int, float]:
    toks = _tokenize(query)
    tf = Counter(toks)
    vec: dict[int, float] = {}
    for term, count in tf.items():
        ti = handle.vocab.get(term)
        if ti is None:
            continue
        vec[ti] = count * handle.idf[ti]
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm > 0:
        for k in list(vec.keys()):
            vec[k] /= norm
    return vec


def _cosine(a: dict[int, float], b: dict[int, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def search(
    stem: str | Path,
    query: str,
    k: int = 5,
    *,
    handle: IndexHandle | None = None,
) -> list[Hit]:
    if handle is None:
        handle = load_index(stem)
    if k <= 0:
        return []
    qv = _query_vector(query, handle)
    if not qv:
        return []
    scored: list[tuple[float, int]] = []
    for i, dv in enumerate(handle.doc_vectors):
        s = _cosine(qv, dv)
        if s > 0:
            scored.append((s, i))
    scored.sort(key=lambda t: (-t[0], t[1]))
    out: list[Hit] = []
    for score, i in scored[:k]:
        row = handle.meta_rows[i]
        out.append(
            Hit(
                chunk_id=row["chunk_id"],
                docket_id=row["docket_id"],
                page_number=row["page_number"],
                line_start=row["line_start"],
                line_end=row["line_end"],
                text=row["text"],
                score=float(score),
            )
        )
    return out
