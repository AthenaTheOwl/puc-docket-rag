"""Fixture loader. v0.1 ships a committed VA docket fixture under
``tests/fixtures/va/PUR-2024-00001/`` as a ``pages.jsonl`` plus a
``fixture.meta.json`` sidecar. A plain-text ``pages.txt`` (with form-feed
or ``<<<PAGE_BREAK>>>`` markers) is also accepted so a stand-alone text
file can be hand-edited in tests.

PDF parsing is deferred: spec 0003+ will add the ``pypdf`` path described
in design B1 once a redistributable PDF lands.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


_FORM_FEED = "\x0c"
_TEXT_MARKER = "<<<PAGE_BREAK>>>"
_PAGE_SPLIT = re.compile(r"\x0c|\n?<<<PAGE_BREAK>>>\n?")

_REQUIRED_META_FIELDS = ("docket_id", "source_url", "retrieved_at", "sha256")


@dataclass(frozen=True)
class FixtureDoc:
    docket_id: str
    source_path: Path
    meta: dict

    def pages(self) -> Iterator[tuple[int, str]]:
        suffix = self.source_path.suffix.lower()
        if suffix == ".jsonl":
            yield from _pages_from_jsonl(self.source_path)
        else:
            yield from _pages_from_text(self.source_path)


def _pages_from_jsonl(path: Path) -> Iterator[tuple[int, str]]:
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                # Name the file and line so a bad row is as actionable as
                # the missing-field branch below, not a bare decode trace.
                raise ValueError(
                    f"{path}:{lineno}: not valid JSON: {e.msg}"
                ) from e
            if "page_number" not in row or "text" not in row:
                raise ValueError(
                    f"{path}:{lineno}: pages.jsonl rows must carry "
                    f"'page_number' and 'text'"
                )
            yield int(row["page_number"]), row["text"]


def _pages_from_text(path: Path) -> Iterator[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    if _FORM_FEED in text or _TEXT_MARKER in text:
        raw_pages = _PAGE_SPLIT.split(text)
    else:
        raw_pages = [text]
    # Page numbers are derived from the order of non-empty segments. A real
    # PDF with blank pages would shift downstream page numbers; the
    # ``pages.jsonl`` path is preferred because it carries authoritative
    # page numbers from the source document.
    page_no = 0
    for page in raw_pages:
        stripped = page.strip("\n")
        if stripped.strip() == "":
            continue
        page_no += 1
        yield page_no, stripped


def _read_meta(meta_path: Path) -> dict:
    if not meta_path.is_file():
        raise FileNotFoundError(
            f"missing fixture.meta.json at {meta_path}; "
            f"spec 0002 R-PDR-V1-002 requires it"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    missing = [f for f in _REQUIRED_META_FIELDS if not meta.get(f)]
    if missing:
        raise ValueError(
            f"{meta_path}: missing required fields "
            f"{missing}; spec R-PDR-V1-002 requires "
            f"{list(_REQUIRED_META_FIELDS)}"
        )
    return meta


def _locate_source(directory: Path) -> Path:
    for name in ("pages.jsonl", "pages.txt"):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    extras = sorted(directory.glob("*.jsonl")) or sorted(directory.glob("*.txt"))
    if extras:
        return extras[0]
    raise FileNotFoundError(
        f"no pages.jsonl or pages.txt under {directory}"
    )


def load_fixture(path: str | Path) -> FixtureDoc:
    """Load a docket fixture.

    ``path`` is normally a fixture directory holding ``pages.jsonl`` (or
    ``pages.txt``) plus a ``fixture.meta.json`` sidecar; both files must
    sit in the same directory. ``fixture.meta.json`` is required (see
    R-PDR-V1-002) and must carry ``docket_id``, ``source_url``,
    ``retrieved_at``, and ``sha256``.

    A ``.jsonl`` or ``.txt`` file path is also accepted; the meta sidecar
    is looked up next to the file under the canonical name
    ``fixture.meta.json``.
    """
    p = Path(path)
    if p.is_dir():
        source = _locate_source(p)
        meta_path = p / "fixture.meta.json"
    else:
        if p.suffix.lower() not in {".jsonl", ".txt"}:
            raise ValueError(
                f"v0.1 fixtures must be .jsonl or .txt; got "
                f"{p.suffix or '(no suffix)'}"
            )
        source = p
        meta_path = source.with_name("fixture.meta.json")

    meta = _read_meta(meta_path)
    docket_id = meta["docket_id"]
    return FixtureDoc(docket_id=docket_id, source_path=source, meta=meta)
