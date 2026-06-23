# Plan: Migrate DataFrames from pandas to Polars (polars-migration)

## Context

`polars>=1.40.1` is a declared dependency but is never imported. All in-memory tabular
data currently flows through **pandas**: query results (`QueryResult.df`), the schema
HUD frames, and exports. The goal is to make **`polars.DataFrame` the canonical DataFrame
type** across the application boundary and remove pandas as a *direct* dependency of the
`wherewolf` package and its tests.

Verified environment facts (do not re-litigate; build on them):

- PySpark **4.1.1** is installed and exposes the public `DataFrame.toArrow()`
  (Spark 4.0+, SPARK-47365) and `SparkSession.createDataFrame(pyarrow.Table)`. Both
  directions round-trip with `pl.from_arrow(...)` / `pl.DataFrame.to_arrow()`. This means
  the Spark engine can be made fully pandas-free with **public** APIs — no third-party
  bridge, no private `_collect_as_arrow`, no pandas hop.
- DuckDB exposes `relation.pl()` to return a Polars DataFrame natively.
- `pyarrow` (23.0.1) is installed. `fastexcel` and `xlsxwriter` are **not** yet installed
  and must be added (`pl.read_excel` needs `fastexcel`; `pl.write_excel` needs `xlsxwriter`).
- The full-result-export feature is already merged: both engines accept `limit=None`
  meaning "no row cap"; preserve that path during the rewrite.

Relevant files: `src/wherewolf/execution/models.py`, `.../duckdb_engine.py`,
`.../spark_engine.py`, `src/wherewolf/export/exporter.py`, `src/wherewolf/app.py`,
`pyproject.toml`, and the corresponding `tests/`.

**Slug used throughout this plan:** `polars-migration`

---

## Orchestration Contract

**Slug:** `polars-migration`

**Plan file:**

```text
docs/plans/2026-06-23_polars-migration.md
```

**Implementation branch:**

```text
feat/polars-migration
```

**Round-complete marker:**

```text
/tmp/wherewolf/polars-migration_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/polars-migration_finalized
```

**Review notes:**

```text
docs/review/polars-migration-review-*.md
```

Each review note ends with exactly one status trailer:

```text
STATUS: CHANGES_REQUESTED
```

or:

```text
STATUS: APPROVED
```

---

## Required Agent Protocol

1. Use the **implementer** skill.
2. Work from the repository root.
3. Branch from `main`.
4. Commit this plan as the first commit on the implementation branch.
5. Follow TDD where behavior changes are testable.
6. Run quality gates before marking any round complete.
7. Do not write your own review.
8. Do not create files under `docs/review/`.
9. Do not delete files under `docs/review/`.
10. Review notes are durable audit records and must be committed.
11. Resolving a review note means:
    - implement the requested changes;
    - run quality gates;
    - commit the code/docs changes;
    - commit the review note itself if it is not already committed;
    - recreate the round-complete marker.
12. After finalization, stop polling and exit cleanly.

---

## Setup

Start from `main`:

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/polars-migration
```

Commit this plan first:

```bash
git add docs/plans/2026-06-23_polars-migration.md
git commit -m "docs(plan): add polars-migration implementation plan"
```

---

## Implementation Tasks

Canonical type after this work: `polars.DataFrame`. No public method signatures change;
only the *type* of the returned/handled DataFrame changes from `pd.DataFrame` to
`pl.DataFrame`. Work in the ordered, atomic steps below. Each step is a Red→Green commit
that keeps the full suite passing — update the relevant tests first, then the source.

Use the existing `is_truncated` semantics unchanged (still fetch `head(limit + 1)` for the
integer-limit path; `limit=None` returns the full result with `is_truncated=False`).

### Step 1 — Add dependencies (`chore(deps)`)

```bash
./run.sh uv add fastexcel xlsxwriter
```

Ensure `pyproject.toml` pins `pyspark>=4.0` (the Arrow APIs require it). Do **not** remove
`pandas` yet — that is the last step, after no module imports it.

### Step 2 — Exporter (`refactor(export)`)

Update `tests/test_exporter.py` first to pass a `pl.DataFrame` and read results back with
Polars (`pl.read_csv`/`pl.read_parquet`/`pl.read_excel` over `io.BytesIO`). Then rewrite
`src/wherewolf/export/exporter.py` to accept `pl.DataFrame` and return `bytes`:

- CSV: `return df.write_csv().encode("utf-8")` (no-path `write_csv` returns `str`).
- Parquet: `buf = io.BytesIO(); df.write_parquet(buf); return buf.getvalue()`.
- Excel: `buf = io.BytesIO(); df.write_excel(buf); return buf.getvalue()` (uses `xlsxwriter`).

Remove the `import pandas as pd` / `openpyxl` writer usage from this module.

### Step 3 — QueryResult model (`refactor(models)`)

In `src/wherewolf/execution/models.py`, change `df` to a Polars frame:
`df: pl.DataFrame = field(default_factory=pl.DataFrame)`. Update `tests/test_models.py`.

### Step 4 — DuckDB engine (`refactor(duckdb)`)

In `src/wherewolf/execution/duckdb_engine.py`:

- Replace `.df()` with `.pl()`: full path `rel.pl()`; preview path
  `rel.limit(limit + 1).pl()`. `.head(limit)` and `len(...)` work on Polars frames.
- `get_schema`: `self.con.sql(f"DESCRIBE {temp_alias}").pl()`, then
  `.select(["column_name", "column_type"]).rename({"column_name": "Column", "column_type": "Type"})`.
  Empty fallback: `pl.DataFrame(schema={"Column": pl.Utf8, "Type": pl.Utf8})`.
- Remove `import pandas as pd`; the return type annotations become `pl.DataFrame`.

Update `tests/test_duckdb_engine.py`, `tests/test_multi_dataset.py`,
`tests/test_duckdb_sql_injection.py`: replace pandas idioms (`df["x"].values` →
`df["x"].to_list()`, `isinstance(df, pd.DataFrame)` → `isinstance(df, pl.DataFrame)`),
and switch any fixture file-writes to `pl.DataFrame(...).write_csv/write_parquet`.

### Step 5 — Spark engine (`refactor(spark)`) — pandas-free via Arrow

In `src/wherewolf/execution/spark_engine.py`:

- In `_get_session`, set `.config("spark.sql.execution.arrow.pyspark.enabled", "true")`.
- Result collection: `pl.from_arrow(res_spark.toArrow())` for `limit=None`, and
  `pl.from_arrow(res_spark.limit(limit + 1).toArrow())` for the integer path. `.head(limit)`
  and `len(...)` then apply to the Polars frame.
- Excel ingestion in `_register_view`: replace the `pd.read_excel` → `createDataFrame`
  bridge with `spark.createDataFrame(pl.read_excel(abs_path).to_arrow())`.
- `get_schema`: build the rows list as today, then
  `pl.DataFrame(rows, schema={"Column": pl.Utf8, "Type": pl.Utf8})`; same empty fallback.
- Remove `import pandas as pd`.

Update the Spark tests (`tests/test_spark_engine_optimization.py`, `tests/test_spark_engine*.py`):
the mocks currently stub `.toPandas()`. Change them to stub `.toArrow()` returning a
`pyarrow.Table` (e.g. `import pyarrow as pa; pa.table({"a": [1, 2]})`), and assert the same
`row_count` / `is_truncated` outcomes. The `limit(limit + 1)` assertion stays for the
integer path; for a `limit=None` test, assert `.toArrow()` is called and `.limit` is not.

### Step 6 — App + dependency removal (`refactor(app)` then `chore(deps)`)

- `src/wherewolf/app.py`: `st.dataframe(result.df)` and the schema HUD already accept
  Polars (Streamlit 1.55). Confirm no pandas-specific calls remain; the filename helper
  uses dict `.values()` (unrelated to DataFrames). Update `tests/test_app_flow.py`
  fixtures to `QueryResult(df=pl.DataFrame(...))`.
- Grep the tree to confirm no `import pandas` / `pd.` / `.toPandas()` remain in `src/` or
  `tests/`. Convert any stragglers (e.g. `tests/test_excel_support.py` should create
  `.xlsx` inputs with `pl.DataFrame(...).write_excel(path)`).
- Then remove pandas as a direct dependency: `./run.sh uv remove pandas`, and remove
  `openpyxl` if nothing else uses it. Run the full suite. If a transitive consumer still
  imports pandas at runtime and a test breaks, keep `pandas`/`openpyxl` only as a dev
  dependency and note why in the commit message; otherwise remove them outright.

### Documentation

- Update `README.md` dependency notes (Polars-based exports; new `fastexcel`/`xlsxwriter`
  deps; pandas no longer a direct dependency).
- Record a session log under `docs/agent_conversations/` per the project protocol.

---

## Quality Gates

Run before marking any round complete:

```bash
scripts/orchestration/run-quality-gates
scripts/orchestration/check-review-notes-not-deleted
git status --short
```

The round is not complete unless:

1. all requested implementation work is done;
2. all relevant tests pass;
3. build/typecheck gates pass;
4. review notes have not been deleted;
5. the working tree is clean;
6. all code/docs changes are committed.

---

## Verification

Automated (must pass before marking the round complete):

- `scripts/orchestration/run-quality-gates` — runs ruff check/format, `ty check src/`,
  and the full `pytest` suite.
- `grep -rn "import pandas\|pd\.\|\.toPandas()" src/ tests/` returns no matches (or only
  a documented, justified dev-only exception).
- DuckDB and Spark `execute(...)` return a `pl.DataFrame` for both the integer-limit and
  `limit=None` paths, with correct `row_count` and `is_truncated`.
- Exporter round-trips: CSV/Parquet/Excel bytes read back via Polars equal the input frame.
- dtype spot-check: a query over a column with nulls and a timestamp/date column exports
  and re-reads without type corruption (Arrow path; note Spark `toArrow()` timestamps
  follow JVM/session timezone).

Deferred / manual:

- Streamlit UI smoke test (`st.dataframe` rendering of a Polars result and the schema HUD)
  is not unit-testable here; verify manually by running the app if needed. State this
  explicitly when marking the round complete.
- Spark integration tests remain `@pytest.mark.skip` (Spark setup is heavy in CI); the
  Spark engine changes are covered by the mock-based tests.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished polars-migration
```

This writes:

```text
/tmp/wherewolf/polars-migration_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer polars-migration`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/polars-migration-review-*.md
```

When a review note exists or a new review note appears:

1. Read the full review note.
2. If the note ends with:

   ```text
   STATUS: CHANGES_REQUESTED
   ```

   then resume work.

3. Clear the round-complete marker:

   ```bash
   scripts/orchestration/clear-finished polars-migration
   ```

4. Address every requested change.
5. Run quality gates:

   ```bash
   scripts/orchestration/run-quality-gates
   scripts/orchestration/check-review-notes-not-deleted
   ```

6. Commit code/docs fixes.
7. Commit the review-note file itself if it is not already committed:

   ```bash
   git add docs/review/polars-migration-review-*.md
   git commit -m "docs(review): record polars-migration review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished polars-migration
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer polars-migration` after the next review note is created.

---

## Approval Handling

If the latest review note ends with:

```text
STATUS: APPROVED
```

then:

1. Confirm every previous review item has been addressed.
2. Confirm all review notes are committed:

   ```bash
   scripts/orchestration/check-review-notes-committed polars-migration
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize polars-migration
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/polars-migration_finalized
   ```

6. Stop polling and exit cleanly.

---

## Review Rules

Do not write your own review.

Do not create files under:

```text
docs/review/
```

Do not delete files under:

```text
docs/review/
```

Only the orchestrator writes review notes. Your job is to read them, resolve them, commit them as audit records, and continue the loop.

---

## Finalization Rules

Only finalize after a review note with:

```text
STATUS: APPROVED
```

Finalization is performed with:

```bash
scripts/orchestration/finalize polars-migration
```

Do not manually merge into `main` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/polars-migration_finished
/tmp/wherewolf/polars-migration_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
