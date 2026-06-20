"""Structured extraction with citation validation.

The ``LLMAdapter`` interface is intentionally minimal: it takes a query
and the retrieved hits, and returns a list of dict rows. The
``FakeAdapter`` ships canned output for v0.1 tests; real adapters land
in spec 0003+.

Schema validation runs against ``schemas/cost_allocation_rule.schema.json``
via a small stdlib validator that covers the subset the schema uses
(``type``, ``required``, ``enum``, ``minLength``, ``minimum``, ``pattern``,
``additionalProperties``). The citation pass enforces the spec-0002
contract: ``source_citation.chunk_id`` MUST match a chunk_id returned by
the retrieval call for that row. Rows failing either check are dropped
and logged to stderr — never patched.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

from pdr.search import Hit, search

DEFAULT_QUERY = "cost allocation methodology"
DEFAULT_K = 5
SUPPORTED_SCHEMAS = {"cost_allocation_rule"}
DEFAULT_SCHEMA_DIR = Path("schemas")
# Schema-valid (40 lowercase hex) but unmistakably synthetic in log
# output. A real chunk_id from `chunk_id_for` is sha1-hex and will
# essentially never collide with the all-zeros sentinel.
FABRICATED_CHUNK_ID = "0" * 40


class LLMAdapter(Protocol):
    name: str

    def extract(
        self, schema: str, query: str, hits: list[Hit]
    ) -> list[dict]: ...


@dataclass
class FakeAdapter:
    """Deterministic adapter for tests and offline runs.

    Emits two rows: one with a valid ``source_citation.chunk_id`` taken
    from the top hit, and one with a deliberately bogus chunk_id so the
    citation-validation pass has something to drop. The bogus marker is
    a string of forty zeros — schema-valid hex so the row reaches the
    citation check, but unmistakable in log output.
    """

    name: str = "fake"

    def extract(
        self, schema: str, query: str, hits: list[Hit]
    ) -> list[dict]:
        if schema != "cost_allocation_rule":
            raise ValueError(f"FakeAdapter does not support schema={schema!r}")
        if not hits:
            return []
        top = hits[0]
        return [
            {
                "rule_id": "CAR-001",
                "rule_text": "Data-center load is allocated to the GS-4 rate class.",
                "source_citation": {
                    "docket_id": top.docket_id,
                    "page_number": top.page_number,
                    "line_range": f"{top.line_start}-{top.line_end}",
                    "chunk_id": top.chunk_id,
                },
            },
            {
                "rule_id": "CAR-002",
                "rule_text": "This row has a fabricated citation and must be dropped.",
                "source_citation": {
                    "docket_id": top.docket_id,
                    "page_number": top.page_number,
                    "line_range": "1-1",
                    "chunk_id": FABRICATED_CHUNK_ID,
                },
            },
        ]


def load_schema(name: str, schema_dir: Path | str | None = None) -> dict:
    base = Path(schema_dir) if schema_dir else DEFAULT_SCHEMA_DIR
    candidates = [base / f"{name}.schema.json"]
    if not base.is_absolute():
        candidates.append(Path(__file__).resolve().parents[2] / base / f"{name}.schema.json")
    for c in candidates:
        if c.is_file():
            return json.loads(c.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        f"could not locate schema {name!r} in {[str(c) for c in candidates]}"
    )


_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "null": (type(None),),
}


def _validate_against_schema(value: Any, schema: dict, path: str) -> str | None:
    """Return None on success, else a short failure reason. Covers the
    JSON-Schema keywords this repo's schemas actually use; a full
    validator is overkill for v0.1. Known scope limits: bool-vs-number
    coercion is only blocked for `"integer"`, and `array.items` is not
    recursed into. Neither keyword is exercised by the current schema;
    spec 0003+ swaps in `jsonschema`.
    """
    expected = schema.get("type")
    if expected:
        types = _TYPE_MAP.get(expected, ())
        if expected == "integer" and isinstance(value, bool):
            return f"{path}: must be int"
        if not isinstance(value, types):
            return f"{path}: must be {expected}"
    if "enum" in schema and value not in schema["enum"]:
        return f"{path}: not in enum {schema['enum']}"
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            return f"{path}: shorter than minLength {schema['minLength']}"
        if "pattern" in schema and not re.search(schema["pattern"], value):
            return f"{path}: does not match pattern {schema['pattern']!r}"
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            return f"{path}: below minimum {schema['minimum']}"
    if expected == "object" and isinstance(value, dict):
        required = schema.get("required", [])
        for field in required:
            if field not in value:
                return f"{path}: missing field {field!r}"
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = set(value.keys()) - set(properties.keys())
            if extras:
                return f"{path}: unexpected fields {sorted(extras)}"
        for key, sub in value.items():
            if key in properties:
                reason = _validate_against_schema(
                    sub, properties[key], f"{path}.{key}"
                )
                if reason:
                    return reason
    return None


def _default_schema() -> dict:
    return load_schema("cost_allocation_rule")


def validate_citations(
    rows: Iterable[dict],
    hits: list[Hit],
    *,
    schema: dict | None = None,
) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Split rows into ``(kept, dropped)``. A row is dropped when it
    fails schema validation or its ``source_citation.chunk_id`` is not
    in the retrieved set. ``schema`` defaults to
    ``cost_allocation_rule.schema.json``.
    """
    if schema is None:
        schema = _default_schema()
    retrieved_ids = {h.chunk_id for h in hits}
    kept: list[dict] = []
    dropped: list[tuple[dict, str]] = []
    for row in rows:
        reason = _validate_against_schema(row, schema, "row")
        if reason:
            dropped.append((row, f"schema: {reason}"))
            continue
        cid = row["source_citation"]["chunk_id"]
        if cid not in retrieved_ids:
            dropped.append((row, f"chunk_id {cid!r} not in retrieved set"))
            continue
        kept.append(row)
    return kept, dropped


def extract(
    stem: str | Path,
    schema: str,
    *,
    adapter: LLMAdapter | None = None,
    query: str = DEFAULT_QUERY,
    k: int = DEFAULT_K,
    schema_dir: Path | str | None = None,
) -> tuple[list[dict], list[tuple[dict, str]]]:
    if schema not in SUPPORTED_SCHEMAS:
        raise ValueError(
            f"unsupported schema {schema!r}; v0.1 supports {sorted(SUPPORTED_SCHEMAS)}"
        )
    adp = adapter or FakeAdapter()
    hits = search(stem, query, k=k)
    raw_rows = adp.extract(schema, query, hits)
    schema_doc = load_schema(schema, schema_dir)
    kept, dropped = validate_citations(raw_rows, hits, schema=schema_doc)
    for row, reason in dropped:
        rid = row.get("rule_id", "<no rule_id>")
        cid = (row.get("source_citation") or {}).get("chunk_id", "<no chunk_id>")
        print(
            f"extract: dropped rule_id={rid} chunk_id={cid}: {reason}",
            file=sys.stderr,
        )
    return kept, dropped


def write_jsonl(rows: list[dict], out_path: str | Path) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p
