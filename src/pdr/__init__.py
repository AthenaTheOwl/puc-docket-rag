"""puc-docket-rag v0.1 — stdlib-only implementation.

See specs/0002-design/ for the v0.1 scope and decisions/DEC-001 for the
citation-faithfulness contract. FAISS and sentence-transformers land in
spec 0003+.
"""

__version__ = "0.1.0"

from pdr.chunk import Chunk, chunk_pages, normalize_text, chunk_id_for
from pdr.ingest import FixtureDoc, load_fixture
from pdr.index import IndexHandle, build_index, load_index
from pdr.search import Hit, search

__all__ = [
    "Chunk",
    "chunk_pages",
    "normalize_text",
    "chunk_id_for",
    "FixtureDoc",
    "load_fixture",
    "IndexHandle",
    "build_index",
    "load_index",
    "Hit",
    "search",
]
