# JSON Lines registration and the dead extension constant

## Problem Definition

Two related defects in how a source file's format is decided.

1. **`.jsonl` files are parsed as CSV.** `SourceFormat.from_path` accepts `.jsonl`
   (`src/wherewolf/domain/enums.py`), the file dialog offers it, the Spark engine handles it, and
   the README advertises JSON Lines support — but `DuckDBEngine._register_view`
   (`src/wherewolf/execution/duckdb_engine.py:16`) has no `.jsonl` branch. Its `else` arm falls
   back to `from_csv_auto`, so a JSON Lines file added to the catalog is silently read as CSV.
   The user sees a single garbage column rather than an error.

2. **`constants.SUPPORTED_EXTENSIONS` is dead and wrong.** Nothing in `src/` reads it; only
   `tests/test_constants.py` does. It also disagrees with the real gate, `SourceFormat.from_path`:
   it lists `.xls` (which `from_path` rejects, making the `.xls` arm of `_register_view` equally
   unreachable) and omits `.jsonl` (which `from_path` accepts). A second, stale definition of
   "supported" is what let defect 1 hide.

The root cause of 1 is the silent `else` fallback: any suffix the engine does not know is guessed
at as CSV rather than reported.

## Architecture Overview

Make `SourceFormat` the single source of truth for format dispatch, everywhere.

- `_register_view` dispatches on `SourceFormat.from_path(path)` instead of on raw suffix strings,
  and has no fallback arm — an unsupported suffix raises `UnsupportedFormatError`, which the
  existing boundaries in `execute` and `get_schema` already normalise into a reported failure.
- `SUPPORTED_EXTENSIONS` is deleted rather than corrected; keeping a second list invites the same
  drift again.
- The one remaining hardcoded extension list, `initialFilter` in
  `desktop/dialogs/file_dialog_service.py:132`, is replaced with the existing `_build_filter()`,
  which already derives from `SourceFormat`.

## Core Data Structures

No new structures. `SourceFormat` (`domain/enums.py`) gains no members; it is already complete
(`csv`, `parquet`, `json`, `jsonl`, `xlsx`) and already raises `UnsupportedFormatError` for
anything else.

## Public Interfaces

- `DuckDBEngine._register_view(path, alias)` — unchanged signature; now raises
  `UnsupportedFormatError` for an unsupported suffix instead of guessing CSV.
- `wherewolf.constants.SUPPORTED_EXTENSIONS` — **removed**. Internal; no runtime caller.
- `SourceFormat.JSON_LINES` registers via `read_json_auto(?, format='newline_delimited')`;
  `SourceFormat.JSON` keeps `read_json_auto(?)` with array detection.
- `.xls` is not, and never was, a supported input: `from_path` rejects it. The unreachable `.xls`
  arm of `_register_view` is removed with it.

## Dependency Requirements

None added. DuckDB's `read_json_auto` and the already-loaded `excel` extension cover every branch.

## Testing Strategy

RED first, in this order:

1. `tests/test_duckdb_engine.py` — write a `.jsonl` fixture with one JSON object per line, query
   it through `DuckDBEngine.execute`, and assert the object's keys come back as separate typed
   columns with correct values. Fails today: the CSV fallback yields one text column.
2. `tests/test_duckdb_engine.py` — `get_schema` on the same `.jsonl` fixture reports the JSON
   fields, not a single CSV-derived column.
3. `tests/test_duckdb_engine.py` — an unsupported suffix (e.g. `.txt`) produces a failed
   `QueryResult` naming the unsupported format rather than a CSV-parsed success.
4. `tests/test_constants.py` — delete `test_supported_extensions`; add an assertion that
   `SUPPORTED_EXTENSIONS` is no longer exported, so the constant cannot quietly return.
5. `tests/test_file_dialog_service.py` — the initial filter passed to `getOpenFileNames` equals the
   built name filter, so the two lists cannot drift again.

Then GREEN: the `_register_view` rewrite, the constant deletion, the `initialFilter` change.

Gates before commit: `ruff check . --fix`, `ruff format .`, `ty check src/`, `pytest`.
