# Plan: Column profiling with optional profile-on-load (column-profiling)

## Context

The schema panel shows `Name`, `Type`, `Nullable`, `Position` — everything obtainable
without reading the data. The first questions an analyst actually asks about an unfamiliar
column are "how many nulls, how many distinct values, what is the range", and answering
them today means hand-writing an aggregate query per column.

DuckDB answers all of it in one statement. **Verified against the installed DuckDB 1.5.5**,
`SUMMARIZE <alias>` returns twelve columns:

```text
column_name, column_type, min, max, approx_unique, avg, std, q25, q50, q75,
count, null_percentage
```

### Cost — measured, not assumed

`SUMMARIZE` is a full scan, unlike `DESCRIBE`. Measured on this machine:

| source | DESCRIBE | SUMMARIZE |
|---|---|---|
| parquet, 100k rows, 0.4 MB | 17 ms | 30 ms |
| parquet, 2M rows, 5.6 MB | 1 ms | 131 ms |
| CSV, 1M rows, 32.5 MB | 54 ms | 179 ms |
| parquet, 60 cols x 50k rows | — | 280 ms |

Cost grows with rows x columns, so it is cheap at ordinary sizes and unbounded in
principle. That shape drives the design: profiling always runs on a worker thread, and
profile-on-load is skipped above a size threshold rather than being allowed to stall the
catalog.

### Facts the UI must respect

- **`approx_unique` is approximate** (HyperLogLog). Presenting it as an exact distinct
  count would be a correctness lie. Label it accordingly.
- `min` and `max` come back as `VARCHAR` regardless of the column's type.
- `null_percentage` is `DECIMAL(9,2)` — a percentage, not a fraction.
- Non-numeric columns return **null** for `avg`, `std`, `q25`, `q50`, `q75`. These must
  render as empty cells, never as the string `None`.

### Engine scope

`SUMMARIZE` is DuckDB syntax. The Spark adapter has no equivalent statement; PySpark
exposes `DataFrame.summary()` with different columns and no null percentage. **Implement
profiling for DuckDB. For Spark, report "profiling is not available for this engine"
explicitly** — do not silently return an empty profile, and do not fabricate a mapping.
Swallowing an unsupported case is the exact defect found earlier in `get_schema`.

**Slug used throughout this plan:** `column-profiling`

---

## Orchestration Contract

**Slug:** `column-profiling`

**Plan file:**

```text
docs/plans/2026-08-02_column-profiling.md
```

**Implementation branch:**

```text
feat/column-profiling
```

**Round-complete marker:**

```text
/tmp/wherewolf/column-profiling_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/column-profiling_finalized
```

**Review notes:**

```text
docs/review/column-profiling-review-*.md
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
3. Branch from `dev`.
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

## Scope discipline

- Implement only the units the plan lists. Do not modify files outside the plan's scope.
- Do not change runtime behavior beyond what the plan specifies. A `refactor` or
  `cleanup` commit must preserve observable behavior.
- Never edit a test's expected value to make a behavior change pass. If a test
  legitimately must change, that change must be required by the plan or a review
  note, and you must record the rationale in the session log.
- If you spot an unrelated improvement, do not make it here — note it in the
  session log for a separate plan.

---

## Setup

Start from `dev`:

```bash
git checkout dev
git pull --ff-only origin dev
git checkout -b feat/column-profiling
```

Commit this plan first:

```bash
git add docs/plans/2026-08-02_column-profiling.md
git commit -m "docs(plan): add column-profiling implementation plan"
```

---

## Implementation Tasks

One commit per task. TDD: failing test first. Tests reach the feature from `MainWindow` the
way a user would, and assert `isVisible()` where visibility is the point.

### Task 1 — domain type for a profile

Add a `ColumnProfile` (column name plus the SUMMARIZE fields) and a `ProfileResult`
carrying `entry_id`, the profiles, and an error field, mirroring how `SchemaResult` already
separates success from `error_type`/`error_message`. Keep it separate from `SchemaResult`:
schema is cheap and automatic, profiling is expensive and optional, and conflating them
would force one to wait on the other.

Model the nullable statistics as `str | None` / `float | None` so "not applicable for this
type" is representable. Test that a VARCHAR column's `avg` round-trips as `None`.

### Task 2 — engine-level profiling

Add `profile_dataset(entry)` to the execution adapters, beside `inspect_schema`.

DuckDB: register the view exactly as `_register_view` already does, run `SUMMARIZE`, map
rows to `ColumnProfile`. Reuse the existing connection-per-operation and cancellation
handling — profiling must be interruptible, since it is the one schema-side operation that
can run long.

Spark: return a `ProfileResult` whose error states plainly that profiling is unsupported
for this engine.

Test against a real fixture file with a mixed-type frame: an integer column, a float
column, a VARCHAR column and a column containing nulls. Assert the null percentage is
correct for the null-bearing column and that the VARCHAR column's numeric statistics are
`None`. Assert the Spark path reports its error rather than returning empty profiles.

### Task 3 — profile worker

Add `ProfileWorker`, modelled directly on `desktop/workers/schema_worker.py`.

**It must be drained in `MainWindow.closeEvent` exactly as `_schema_workers` is**
(`main_window.py:919-923`). A QThread still running at shutdown delivers posted events into
freed memory — that was a real SIGSEGV in this codebase, and the drain is why it stopped.
Add `_profile_workers` alongside `_schema_workers` and quit/wait both.

Test that a completed worker removes itself from the list, and that `closeEvent` with a
running worker leaves the list empty.

### Task 4 — show the profile in the schema panel

Extend the schema panel to display profile data for the selected dataset, with a
**Profile** button that requests it on demand. The panel already names its dataset and has
a dataset selector; profiling follows the selection.

Present: null %, approximate distinct, min, max, and mean where applicable. **Label the
distinct count as approximate** — "Distinct (approx.)" or equivalent. Blank cells for
statistics that do not apply.

Show a pending state while the worker runs, and the error text when profiling fails or is
unsupported.

Test: with a profiled dataset the panel exposes the null percentage and the approximate
distinct count for a named column; with a VARCHAR column the mean cell is empty; the
approximate label is present in the visible header text.

### Task 5 — profile-on-load preference

Add two settings through `SettingsService`, following the existing key/schema-version
pattern:

- `profile_on_load` (bool) — **default on**
- `profile_max_bytes` (int) — **default 268435456 (256 MB)**

When `profile_on_load` is enabled, adding a dataset queues profiling on the worker right
after schema inspection. When the source exceeds `profile_max_bytes`, skip it and say so in
the panel, leaving the manual Profile button available.

**Why default on with a guard rather than default off:** at the measured sizes above,
profiling costs 30–280 ms on a background thread, which is well inside what a user will not
notice, and the feature is worthless if nobody finds the switch. The threshold bounds the
unbounded case. This differs deliberately from the update check, which defaults off because
it leaves the machine.

Expose both in the Preferences dialog beside the completion settings.

Test: the default is on; with it on, adding a dataset queues profile work; with it off, no
profile work is queued and the manual button still works; a source above the threshold is
skipped with a visible explanation. Assert on work actually being queued, not on the
setting's value alone.

### Task 6 — re-profile when the source changes

`registry._source_warnings` already detects a source file that changed on disk. A profile
computed from stale contents is worse than none, because it looks authoritative. Mark a
displayed profile as stale when the source has changed, and offer re-profiling.

Test that a profile is marked stale after the underlying file's mtime/size changes.

### Cross-cutting requirements

- Do not weaken, skip or delete existing tests.
- Do not make schema inspection wait on profiling — opening a dataset must stay fast.
- Do not present `approx_unique` as exact.
- Do not remove `timid = true`, the `pyarrow` import, or the overwrite confirmation.
- Do not change `EngineKind` or the sqlglot identifiers in `DIALECT_MAPPING`.
- Do not bump the version, tag, or touch `main`.
- Run `./run.sh uv run ty check .` (whole repo) before committing.

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

```bash
./run.sh uv run ruff check . && ./run.sh uv run ruff format --check .
./run.sh uv run ty check .
./run.sh uv run pytest
```

Record in the session log:

1. A full `ProfileResult` for a mixed-type fixture, showing `None` statistics on the
   VARCHAR column and the correct null percentage on the null-bearing column.
2. The Spark path's error message.
3. `_profile_workers` length after a worker finishes, and after `closeEvent` with one running.
4. The panel's visible header text including the approximate-distinct label, and one row's
   cells for a VARCHAR column.
5. `profile_on_load` default; whether profile work is queued with it on and with it off.
6. Behaviour for a source above `profile_max_bytes`, including the message shown.
7. Wall-clock time for schema inspection with profiling on, versus off, on a ~1M row CSV —
   to demonstrate the catalog is not stalled.

**Negative controls are mandatory for tasks 2, 3, 5 and 6**, run against the **full** suite:
make the DuckDB profile return empty and confirm task 2 fails; remove the `_profile_workers`
drain from `closeEvent` and confirm task 3 fails; flip the `profile_on_load` default and
confirm task 5 fails; suppress the stale marking and confirm task 6 fails.

Confirm each mutation actually modified the file before trusting its result. Repeatedly this
session a mutation that failed to apply looked exactly like a guard that does not bite — if a
mutation reports no failures, first prove it changed the code.

## Deferred

Exact distinct counts (`COUNT(DISTINCT)`) are deliberately out of scope: `SUMMARIZE` gives an
approximation for free, and an exact count is a second full pass per column. Histograms,
per-column value frequencies, and profiling for Spark are also out of scope. How the profile
columns look at narrow panel widths is a manual maintainer check.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished column-profiling
```

This writes:

```text
/tmp/wherewolf/column-profiling_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer column-profiling`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/column-profiling-review-*.md
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
   scripts/orchestration/clear-finished column-profiling
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
   git add docs/review/column-profiling-review-*.md
   git commit -m "docs(review): record column-profiling review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished column-profiling
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer column-profiling` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed column-profiling
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize column-profiling
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/column-profiling_finalized
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
scripts/orchestration/finalize column-profiling
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/column-profiling_finished
/tmp/wherewolf/column-profiling_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
