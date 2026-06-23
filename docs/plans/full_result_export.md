# Full Result Export

## Problem Definition

The download/export controls in `app.py` serialize `result.df`, which is the
**preview** DataFrame produced by `engine.execute(..., limit=preview_limit)`.
Both engines truncate to `limit` rows (`head(limit)`), so any export of a
truncated result silently omits rows beyond the preview size (10–1000). Users
expect a saved file to contain the full result set, not just the preview.

## Architecture Overview

1. Engines (`DuckDBEngine`, `SparkEngine`) gain support for an unbounded fetch:
   `limit=None` means "return the entire result set" (no `LIMIT`, `is_truncated`
   always `False`). The existing integer path is unchanged.
2. `app.py` records the engine-dialect query actually executed and the engine
   name at submit time, so a full export can re-run the exact query.
3. The export section keeps the existing (preview) download button and, when the
   result is truncated, adds a "Prepare full export" button that re-runs the
   query with `limit=None`, encodes the full DataFrame in the chosen format, and
   exposes it via a second download button.

## Core Data Structures

- `QueryResult` (unchanged): `df`, `row_count`, `is_truncated`, etc.
- `st.session_state.full_export`: `{data, mime, file_name, rows, format}` cache
  of the most recently prepared full export.

## Public Interfaces

- `DuckDBEngine.execute(query, path="", limit: int | None = 1000, catalog=None)`
- `SparkEngine.execute(query, path="", limit: int | None = 1000, catalog=None)`
  - `limit=None` → full result set, `is_truncated=False`.

## Dependency Requirements

None. Reuses existing `Exporter`, DuckDB, and PySpark.

## Testing Strategy

- DuckDB (integration): with a 5-row CSV, `limit=2` truncates; `limit=None`
  returns all 5 rows with `is_truncated=False`.
- Spark (mock): `limit=None` calls `toPandas()` directly on the result frame and
  does not call `limit(...)`.
- App wiring is verified manually (Streamlit UI not unit-testable here).
