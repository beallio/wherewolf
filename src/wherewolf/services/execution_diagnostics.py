"""Fail-closed parsing of exact DuckDB source locations from error text."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DuckDbErrorLocation:
    """A one-based location and source excerpt relative to executed DuckDB SQL."""

    line: int
    column: int
    source_excerpt: str


_SOURCE_LINE = re.compile(r"^LINE (?P<line>[1-9][0-9]*): (?P<source>.*)$")
_CARET_LINE = re.compile(r"^(?P<indent> *)\^$")


def parse_duckdb_error_location(message: str) -> DuckDbErrorLocation | None:
    """Return DuckDB's final unambiguous ``LINE``/caret location, if available.

    DuckDB aligns the caret with the full rendered ``LINE n: `` prefix.  The
    parser only translates that display position into a source column when the
    source text is safe to count codepoint-by-codepoint; the caller still has
    to compare ``source_excerpt`` against the SQL it executed before navigating.
    """
    candidates: list[DuckDbErrorLocation] = []
    lines = message.splitlines()

    for index, rendered_line in enumerate(lines[:-1]):
        source_match = _SOURCE_LINE.fullmatch(rendered_line)
        if source_match is None:
            continue

        caret_match = _CARET_LINE.fullmatch(lines[index + 1])
        if caret_match is None:
            continue

        source = source_match.group("source")
        prefix_width = len(f"LINE {source_match.group('line')}: ")
        caret_offset = len(caret_match.group("indent"))
        source_offset = caret_offset - prefix_width
        if not source or source_offset < 0 or source_offset >= len(source):
            continue
        if "\t" in source or "…" in source or "..." in source:
            continue
        if not source[:source_offset].isascii():
            continue

        candidates.append(
            DuckDbErrorLocation(
                line=int(source_match.group("line")),
                column=source_offset + 1,
                source_excerpt=source,
            )
        )

    return candidates[-1] if candidates else None


__all__ = ["DuckDbErrorLocation", "parse_duckdb_error_location"]
