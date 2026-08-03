# Phase 12 — Path-based export

Slug: `path-based-export`
Base branch: `dev`
Target release: 0.6.0 (minor). **Do not bump the version in this phase.**

## Context

The desktop app can run a query and show a preview. It cannot yet save results. This phase adds
export — **to a path, streamed**, never by building the whole result in memory first.

Goal, from the migration document: **exported files reopen and match expected
rows/columns/order; full DuckDB CSV/Parquet export does not materialize the entire result as a
Polars DataFrame plus bytes; a failed export does not corrupt the destination.**

### The two exports are different things — do not merge them

| | source | mechanism | size |
|---|---|---|---|
| **Preview export** | the `QueryResult.frame` already in memory | write the frame (or a selection of it) to a path | bounded by `preview_limit` |
| **Full export** | the captured `ExecutionRequest` | **re-execute** and stream straight to disk | unbounded |

Full export must **never** load the complete result into Python. That is the exit criterion,
and it is the whole reason this phase exists.

### What already exists — use it, do not rebuild it

- **`export/exporter.py`** — `Exporter.to_csv/to_excel/to_parquet` return **bytes**. It is used
  **only** by `src/wherewolf/ui/results.py` (Streamlit) and `tests/test_exporter.py`.
  **It is Streamlit-owned. Do not modify it, do not extend it, do not route desktop export
  through it.** Returning bytes is precisely the anti-pattern this phase replaces. Write new
  path-based code alongside it.
- **`domain/models.py`** — `ExecutionRequest(request_id, engine, source_dialect, original_sql,
  executable_sql, catalog, preview_limit, submitted_at)` is an immutable snapshot and already
  carries **everything full export needs**: the exact SQL to re-run and the catalog bindings to
  register. `QueryController` emits it alongside each result. **This is the captured request the
  plan refers to — do not re-derive it from the editor**, which may have changed since.
- **`execution/registry.py`** — `_DuckDBAdapter` opens a per-request `:memory:` connection and
  registers catalog views. Full export belongs here: same connection lifecycle, same
  cancellation handle. `DuckDBEngine` (the legacy Streamlit engine) has **no** COPY support and
  **must not be modified**.
- **`desktop/dialogs/file_dialog_service.py`** — `FileDialogService` currently exposes only
  `choose_dataset_files` (an **open** dialog). A **save** dialog is new; follow the existing
  protocol/implementation split so tests can inject a fake.
- **`desktop/clipboard_serializers.py`** — already solves "visual column order" and
  "hidden columns excluded" for copy. Selection export has the same requirement.
  **Reuse that logic; do not write a second implementation that can drift.**
- **`desktop/query_controller.py`** — `shutdown()`, worker tracking and `CancellationHandle`
  are established patterns. Export cancellation should look like execution cancellation.
- **`storage/history.py`** — the atomic write (`tempfile.mkstemp` + `os.replace`) is the
  reference pattern for "a failed write must not corrupt the destination".

### Known defects you must NOT fix here

- `execution/spark_engine.py` swallows exceptions in `get_schema`. Phase 13.
- Streamlit's byte-based export. Phase 14 deletes it.

### Hard constraint: Streamlit must keep working

Do not modify `src/wherewolf/app.py`, `engines.py`, `ui/`, `export/`, `storage/`,
`constants.py` or `.streamlit/`. **`export/` is fully protected this phase** — unlike Phase 11
with `history.py`, there is no exception here. Desktop export is new code in new files.

### Python floor: 3.12 AND 3.14

CI tests both legs. No PEP 758 unparenthesized `except` — write `except (OSError, ValueError):`.
No 3.13+/3.14-only constructs. Let `ruff check --fix` and `ruff format` enforce it.

`./run.sh uv run --python 3.12 ...` re-syncs the **shared** `UV_PROJECT_ENVIRONMENT` at
`/tmp/wherewolf/.venv`. Afterwards run `./run.sh uv sync --all-extras --dev --python 3.14`, or
every later measurement silently runs on the wrong interpreter.

### The crash history you must respect

A native segfault was root-caused in Phase 8: QThreads destroyed while running, posted events
delivered into freed memory. This phase adds an **export worker** — a new background thread.
Any QObject parented to a transient window must not outlive it; anything you start must be
awaited on shutdown, the way `QueryController.shutdown()` and the `_schema_workers` drain do.
**V11 is mandatory this phase.** Do not remove `timid = true` — load-bearing on 3.14.

### Repo mechanics that will fail your commits

- `scripts/check_tdd.sh` requires a **flat** `tests/test_<basename>.py` per staged
  `src/**/*.py`. `src/wherewolf/services/export_service.py` needs `tests/test_export_service.py`.
- The pre-commit hook runs `ruff check`, `ruff format`, `ty check`, `pytest` and
  `check_tdd.sh`, and does `git add -u`, sweeping modified tracked files into your commit.
- Caches live under `/tmp/wherewolf`. Run project commands through `./run.sh`.
- Commit messages must NOT contain `Co-Authored-By:` or `Claude-Session:` trailers.
- **Never write test output to the user's real home.** `tests/conftest.py` has an autouse
  fixture isolating history and `QSettings`; export tests must use `tmp_path` for every
  destination.

### Recording rule — read before writing the session log

**"Not measured" is a complete and acceptable answer.** If you did not run something, say so.
A plausible-looking number never observed is the one thing the record cannot absorb. After any
change you report, run the command that would fail if it had not landed and paste that output.
Record measured values, never adjectives like "all green".

### Baseline

`dev` @ `aaeb8af`: **334 passed, 1 skipped** on both 3.12 and 3.14; CI green on `lint`,
`test (3.12)`, `test (3.14)`. Record your own baseline in Task 1.

## Orchestration Contract

**Slug:** `path-based-export`

**Plan file:**

```text
docs/plans/2026-08-01_path-based-export.md
```

**Implementation branch:**

```text
feat/path-based-export
```

**Round-complete marker:**

```text
/tmp/wherewolf/path-based-export_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/path-based-export_finalized
```

**Review notes:**

```text
docs/review/path-based-export-review-*.md
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

## Setup

Start from `dev`:

```bash
git checkout dev
git pull --ff-only origin dev
git checkout -b feat/path-based-export
```

Commit this plan first:

```bash
git add docs/plans/2026-08-01_path-based-export.md
git commit -m "docs(plan): add path-based-export implementation plan"
```

---

## Implementation Tasks

Each task is one commit, Red before Green. Tasks 2–8 are **Qt-free** — the entire export
mechanism lands testable before any dialog or worker exists.

### Task 1 — Session log and baseline
Create `docs/agent_conversations/2026-08-01_path-based-export.md` with the baseline commit and
the measured tally on **both** interpreters. No source changes.
Commit: `docs: record path-based export baseline`.

### Task 2 — Destination normalization
**Red** (`tests/test_export_destination.py`): a path with no extension gains the one implied by
the chosen format; a path with the **wrong** extension is corrected or rejected per a **stated**
rule; a path already correct is unchanged; case-insensitive match (`.CSV`); the format→filter
string used by the save dialog is derived from one source, not duplicated.
**Green**: `src/wherewolf/services/export_destination.py`, pure functions.
Commit: `feat(export): normalize export destinations and filters`.

### Task 3 — Atomic destination writes
**Red**: writing to a **new** path produces the file; writing to an **existing** path replaces
it only on success; a writer that raises partway leaves the **original file byte-identical**
and leaves **no** temp file behind. Assert the original's bytes, not just its existence.
**Green**: write to a temp file in the destination directory, then `os.replace`. Mirror
`storage/history.py`. Clean up the temp file in `finally`.
Commit: `feat(export): write exports atomically`.

### Task 4 — Preview writers: CSV, XLSX, Parquet
**Red** (`tests/test_preview_export.py`): each format writes a real file that **reopens** and
matches row count, column names and **row order**. Read the file back with polars and compare —
do not assert only that the file is non-empty.
**Green**: `src/wherewolf/services/preview_export.py` writing a `pl.DataFrame` to a path.
**Do not use `export/exporter.py`.**
Commit: `feat(export): add preview writers for csv, xlsx and parquet`.

### Task 5 — Selection export respects visual order
**Red**: exporting a selection honours moved columns and excludes hidden ones — the same rules
as clipboard copy; a discontiguous selection exports per the stated rule.
**Green**: reuse `clipboard_serializers`' ordering logic. **Do not duplicate it** — if it needs
to be shared, extract it once and have both call sites use it.
Commit: `feat(export): export the current selection in visual order`.

### Task 6 — Full export streams via DuckDB COPY
**Red** (`tests/test_full_export.py`): full CSV and Parquet export of a query over a real temp
file produces a file that reopens with the **full** row count — deliberately **more rows than
`preview_limit`**, so a preview-shaped result cannot pass.
**And prove it streams:** assert the adapter issues a `COPY ... TO` statement and that **no
materialisation call** (`.pl()`, `.arrow()`, `.fetchall()`, `.df()`) happens on the full-export
path. Spy on the connection. This is the exit criterion — a test that only checks the output
file cannot distinguish streaming from materialising.
**Green**: extend `_DuckDBAdapter` in `execution/registry.py` with a path-based export using
`COPY (<executable_sql>) TO '<path>' (FORMAT ...)`. Reuse the request-scoped connection and its
cancellation handle. **Do not modify `DuckDBEngine`.**
Commit: `feat(execution): stream full results to disk via duckdb copy`.

### Task 7 — XLSX has no streaming path: guard it
**Red**: requesting a **full** XLSX export of a result larger than a stated threshold is
refused with a clear message naming the limit and suggesting CSV/Parquet; below the threshold it
succeeds; **preview** XLSX is unaffected.
**Green**: enforce the guard. State the threshold and why in the session log.
Commit: `feat(export): guard full xlsx export by size`.

### Task 8 — Warn when sources changed since the query ran
**Red**: if a catalog file's size or mtime differs from when the `ExecutionRequest` was
captured, full export reports a clear warning naming the file; unchanged sources produce no
warning; a **deleted** source is reported rather than crashing.
**Green**: capture the metadata at request time; compare at export time. State whether the
warning blocks or merely informs — and test that behaviour.
Commit: `feat(export): warn when sources changed since execution`.

### Task 9 — Export controller and worker
**Red** (`tests/test_export_controller.py`, `qtbot`): emits a terminal result exactly once;
publishes a cancellation handle **before** work starts; a failure surfaces as a failed export,
not an exception. Use `qtbot.waitSignal` and `worker.wait(...)` — **no sleeps**.
**Green**: `src/wherewolf/desktop/export_controller.py`, mirroring `QueryController`, with a
`shutdown()` that quits and waits for its worker.
Commit: `feat(desktop): add export controller`.

### Task 10 — Cancellation is truthful
**Red**: cancelling mid-export leaves **no partial file at the destination**, an existing
destination untouched, and no temp file behind; cancelling a finished export is safe.
**Green**: wire cancellation to the request-scoped handle.
Commit: `feat(export): cancel exports without leaving partial files`.

### Task 11 — Native save dialog
**Red** (`tests/test_file_dialog_service.py`): a **cancelled** dialog performs no write and
leaves the destination untouched; the returned path is normalized via Task 2; the filter offers
the supported formats.
**Green**: add a save method to `FileDialogService` following the existing protocol/fake split.
Overwrite confirmation is the native dialog's job — assert the flag is requested rather than
reimplementing the prompt.
Commit: `feat(desktop): add native export save dialog`.

### Task 12 — Wire into `MainWindow` with progress and cancel
**Red** (`tests/test_main_window.py`): export actions are disabled with no result and enabled
with one; a successful export reports the destination; a failure reports the reason; cancel is
available while exporting. `closeEvent` must call the controller's `shutdown()`.
**Green**: wire actions, progress and cancel. **Re-run V11 after this task** — it touches
`closeEvent`.
Commit: `feat(desktop): wire export actions with progress and cancel`.

### Task 13 — README and close out
Document both export kinds and **state plainly that full export streams while preview export
does not**. Document the XLSX guard. Bump the README `cacheBuster` per AGENTS.md §13. Finalise
the session log with measured results.
Commit: `docs: document path-based export`.

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

State sample sizes and decision rules **before** measuring. Record measured outcomes.

### V1 — Suite and gates, on BOTH interpreters
```bash
./run.sh uv run pytest -q                         # 3.14 — record the tally
scripts/orchestration/run-quality-gates           # must exit 0
./run.sh uv run --python 3.12 pytest -q --no-cov  # 3.12 — record the tally
./run.sh uv sync --all-extras --dev --python 3.14 # restore the dev interpreter
```

### V2 — Streamlit path untouched
```bash
git diff dev..HEAD -- src/wherewolf/app.py src/wherewolf/engines.py src/wherewolf/ui/ \
  src/wherewolf/export/ src/wherewolf/storage/ src/wherewolf/constants.py .streamlit/
```
**Must be empty.** `export/` is fully protected this phase.

### V3 — Exported files reopen and match (exit criterion)
Read every exported file back and compare row count, column names and **row order** against the
source. **Failure looks like:** asserting the file exists or is non-empty.

### V4 — Full export streams (exit criterion)
Assert both: a `COPY ... TO` statement is issued, **and** no `.pl()`/`.arrow()`/`.fetchall()`/
`.df()` call occurs on the full-export path. Export **more rows than `preview_limit`** so a
preview-shaped result cannot masquerade as a full one. **Failure looks like:** a test that only
inspects the output file — it cannot tell streaming from materialising.

### V5 — Failed export leaves the destination intact (exit criterion)
Assert the pre-existing file is **byte-identical** after a failed export, and that no temp file
remains in the destination directory.

### V6 — Cancellation leaves nothing behind
No partial destination file, no temp file, existing destination untouched.

### V7 — Save-dialog cancellation is a no-op
No file written, no exception.

### V8 — Mutation checks: prove the new tests bite
**Commit first.** Confirm each mutation applied (`git diff --quiet` must be **false**) before
trusting a "no bite"; grep with `--color=no`; revert between each; `git status --short` clean
afterwards. **Record the failing node id you actually observed.**

1. Materialise the full export via `.pl()` and write bytes → the V4 streaming test must FAIL.
2. Write directly to the destination instead of temp-then-replace → the failed-export test
   must FAIL.
3. Ignore visual column order on selection export → that test must FAIL.
4. Skip extension normalization → that test must FAIL.
5. Leave the temp file behind on error → the cleanup test must FAIL.
6. Treat a cancelled save dialog as an empty path and write anyway → the V7 test must FAIL.

Mutation 1 is the most important in this phase — it is the exit criterion.

### V9 — No 3.14-only syntax
```bash
grep -rn "except [A-Za-z_.]*, [A-Za-z_.]*:" src/ tests/ || echo "OK: none"
```

### V10 — No test writes outside tmp_path
Every export destination in tests must be under `tmp_path`. Confirm no test writes to the real
home directory.

### V11 — No native crash regression (mandatory this phase)
```bash
scripts/check_flake.sh 25    # run TWICE; 50 runs total
```
**Pass:** 0 native crashes in 50. This phase adds a background worker and touches `closeEvent`.

`check_flake.sh` overwrites `/tmp/wherewolf/flake-guard-last.txt` every run — **preserve
per-run logs** or you report a count with no evidence. A single clean batch of 25 proves little:
at a 6% rate, `0/25` happens ~21% of the time for code that still crashes.

### Deferred and explicitly NOT verified
- **No human has exported a file from a real window.** All Qt tests are offscreen. Say so.
- **No large-scale export was measured.** Streaming is verified structurally (COPY issued, no
  materialisation call), **not** by exporting a multi-gigabyte result. Say so plainly rather
  than implying a memory measurement was taken.
- Spark export unverified — DuckDB only.
- macOS and Windows unverified; native save dialogs differ per platform.
- Phase 13 is Spark, Phase 14 removes Streamlit.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests. Do
not modify `export/exporter.py`, `DuckDBEngine`, or any Streamlit path. Do not route desktop
export through the byte-based `Exporter`. Do not touch `main`. Do not bump the package version.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished path-based-export
```

This writes:

```text
/tmp/wherewolf/path-based-export_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer path-based-export`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/path-based-export-review-*.md
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
   scripts/orchestration/clear-finished path-based-export
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
   git add docs/review/path-based-export-review-*.md
   git commit -m "docs(review): record path-based-export review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished path-based-export
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer path-based-export` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed path-based-export
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize path-based-export
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/path-based-export_finalized
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
scripts/orchestration/finalize path-based-export
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/path-based-export_finished
/tmp/wherewolf/path-based-export_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
