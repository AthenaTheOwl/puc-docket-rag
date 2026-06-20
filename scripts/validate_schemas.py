"""validate_schemas: parse every JSON Schema under `schemas/`.

A v0.1 gate: confirm each `*.schema.json` file under `schemas/` parses
as JSON and carries the minimum keys a draft-2020-12 schema needs
(`$schema`, `type`, `properties`). Exits non-zero on a parse error or
on a missing key. Stdlib only so it can run from a clean clone with no
third-party validator installed; spec 0003+ will swap to `jsonschema`
once the project takes on dependencies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_KEYS = ("$schema", "title", "type")
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "schemas"


def validate_schema_file(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{path}: top-level value must be an object"]
    for key in REQUIRED_KEYS:
        if key not in data:
            problems.append(f"{path}: missing required key {key!r}")
    if data.get("type") == "object" and "properties" not in data:
        problems.append(f"{path}: object schema must define 'properties'")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args:
        roots = [Path(a) for a in args]
    else:
        roots = [DEFAULT_DIR]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        if not root.is_dir():
            print(f"validate_schemas: path not found: {root}", file=sys.stderr)
            return 2
        files.extend(sorted(root.rglob("*.schema.json")))
    if not files:
        print("validate_schemas: no *.schema.json files found", file=sys.stderr)
        return 2
    all_problems: list[str] = []
    for f in files:
        all_problems.extend(validate_schema_file(f))
    if all_problems:
        for p in all_problems:
            print(p)
        print(
            f"validate_schemas: FAIL ({len(all_problems)} problem(s))",
            file=sys.stderr,
        )
        return 1
    print(f"validate_schemas: OK ({len(files)} schema(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
