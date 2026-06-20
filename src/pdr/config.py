"""``pdr.toml`` loader.

The CLI consults ``load_config`` for default chunk / index / embedding /
extraction values. Explicit CLI flags override the file. The ``[chunk]``
and ``[index]`` sections are the same ones the indexer hashes into the
idempotency sidecar's ``config_hash`` (see ``pdr.index.IndexConfig``).

v0.1 reads a single ``pdr.toml`` at the repo root; per-state overlays
land with the multi-state ingest in spec 0004.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("pdr.toml")


@dataclass(frozen=True)
class ChunkConfig:
    target_tokens: int = 800
    overlap_tokens: int = 100


@dataclass(frozen=True)
class IndexFileConfig:
    min_df: int = 1
    embedding_model_id: str = "stdlib-tfidf-v1"


@dataclass(frozen=True)
class EmbeddingConfig:
    model_id: str = "stdlib-tfidf-v1"
    cache_dir: str = "~/.cache/huggingface"


@dataclass(frozen=True)
class ExtractionConfig:
    default_query: str = "cost allocation methodology"
    default_k: int = 5
    schema_dir: str = "schemas"


@dataclass(frozen=True)
class Config:
    chunk: ChunkConfig = field(default_factory=ChunkConfig)
    index: IndexFileConfig = field(default_factory=IndexFileConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    source_path: Path | None = None


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    section = data.get(name) or {}
    if not isinstance(section, dict):
        raise ValueError(f"pdr.toml: [{name}] must be a table")
    return section


def load_config(path: str | Path | None = None) -> Config:
    """Load ``pdr.toml`` from ``path`` (defaults to ``pdr.toml`` next to
    the current working directory). Missing file returns defaults.
    """
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.is_file():
        return Config(source_path=None)
    with p.open("rb") as f:
        data = tomllib.load(f)
    chunk = _section(data, "chunk")
    index = _section(data, "index")
    embedding = _section(data, "embedding")
    extraction = _section(data, "extraction")
    return Config(
        chunk=ChunkConfig(
            target_tokens=int(chunk.get("target_tokens", 800)),
            overlap_tokens=int(chunk.get("overlap_tokens", 100)),
        ),
        index=IndexFileConfig(
            min_df=int(index.get("min_df", 1)),
            embedding_model_id=str(
                index.get("embedding_model_id", "stdlib-tfidf-v1")
            ),
        ),
        embedding=EmbeddingConfig(
            model_id=str(embedding.get("model_id", "stdlib-tfidf-v1")),
            cache_dir=os.path.expanduser(
                str(embedding.get("cache_dir", "~/.cache/huggingface"))
            ),
        ),
        extraction=ExtractionConfig(
            default_query=str(
                extraction.get("default_query", "cost allocation methodology")
            ),
            default_k=int(extraction.get("default_k", 5)),
            schema_dir=str(extraction.get("schema_dir", "schemas")),
        ),
        source_path=p,
    )
