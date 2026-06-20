"""voice_lint: flag banned marketing terms in prose surfaces.

The banned set is taken from `AGENTS.md` ("Voice constraints"). The
linter scans each `.md` / `.txt` / `.astro` file under the given paths,
prints `path:line:term`, and exits non-zero if any match is found.
Designed to run under stdlib only so it can gate from a clean clone.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BANNED_TERMS = (
    "leverage",
    "synergy",
    "best-in-class",
    "seamless",
    "cutting-edge",
)
SCAN_SUFFIXES = {".md", ".txt", ".astro"}
# Word-boundary match so "leverage" hits but "deleverage" or a code
# identifier doesn't trip the gate. Hyphenated terms keep their dashes.
_PATTERNS = [
    (term, re.compile(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", re.IGNORECASE))
    for term in BANNED_TERMS
]


def _iter_files(root: Path):
    if root.is_file():
        if root.suffix.lower() in SCAN_SUFFIXES:
            yield root
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SCAN_SUFFIXES:
            yield path


def lint_path(root: Path) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in _iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for term, pattern in _PATTERNS:
                if pattern.search(line):
                    hits.append((path, lineno, term))
    return hits


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(
            "usage: voice_lint.py <path> [<path> ...]\n"
            "scans .md/.txt/.astro files for banned marketing terms.",
            file=sys.stderr,
        )
        return 2
    repo_root = Path(__file__).resolve().parent.parent
    all_hits: list[tuple[Path, int, str]] = []
    scanned_any = False
    for raw in args:
        target = Path(raw)
        if not target.exists():
            print(f"voice_lint: path not found: {target}", file=sys.stderr)
            return 2
        scanned_any = True
        all_hits.extend(lint_path(target))
    if not scanned_any:
        return 2
    if not all_hits:
        print("voice_lint: OK")
        return 0
    for path, lineno, term in all_hits:
        try:
            rel = path.relative_to(repo_root)
        except ValueError:
            rel = path
        print(f"{rel}:{lineno}:{term}")
    print(f"voice_lint: FAIL ({len(all_hits)} hit(s))", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
