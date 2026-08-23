# Plan: Count All Query Rows (count-all-rows)

## Context

### Problem Definition

Wherewolf intentionally materializes only a bounded preview. When a result exceeds the configured
limit, the UI says it is truncated but cannot answer the immediate question: how many rows did the
captured query actually return? Users must edit the SQL into a manual `count(*)` wrapper, which
replaces the result they were inspecting and creates an unrelated history entry.

Presentation primitives already exist. `QueryResult.total_row_count` is wired to the result summary,
and the full-XLSX export path already wraps `request.executable_sql` in `SELECT count(*) FROM (...)`
with the captured parameters. The missing work is isolation: `QueryController` is single-slot and
routes every result through the grid, Messages, and history, so a count must not use it.

### Intended Outcome

For a successful truncated DuckDB preview, show an inline **Count all rows** button next to the
truncation explanation. Activating it runs an independent, cancellable background count against the
captured `ExecutionRequest`. Success updates only that editor tab's `total_row_count`, producing the
existing `showing <preview> of <total> rows` summary while preserving the grid, filter, local sort,
selection, original request, export behavior, and history.

This v1 is DuckDB-only. Spark, multi-statement requests, non-truncated results, failures, and
cancelled queries do not offer the button. If any captured source changed or disappeared after the
preview, fail closed with an inline instruction to rerun the query; never display a count for data
different from the visible preview.

### Architecture Overview

- Add `count_rows(request)` to the request-scoped DuckDB adapter as an optional capability rather
  than expanding the cross-engine `ExecutionEngine` protocol. It validates exactly one statement,
  removes only a final statement terminator, re-registers the captured catalog, preserves bound
  parameter order, and executes
  `SELECT count(*) FROM (<captured SQL>) AS _wherewolf_count`. The adapter normalizes success,
  DuckDB failure, and cancellation into a domain `RowCountResult`.
- Add `src/wherewolf/desktop/row_count_controller.py`, modeled on `ExportController`, with a
  `RowCountWorker`, immutable `RowCountResult`, request-id correlation, cancellation-handle
  publication, one active worker, and bounded shutdown. The worker obtains the adapter capability
  through a checked protocol/`getattr`, catches only unexpected adapter-boundary crashes, and always
  closes it.
- Add per-tab row-count status to `_EditorTabState`. `MainWindow` submits the tab's existing
  `last_request`; on completion it finds the tab whose current request ID still matches, ignores
  stale results, and uses `dataclasses.replace` on the frozen `QueryResult` to set
  `total_row_count`. For the current tab it updates only `_last_result`, the summary, and count
  controls through a summary-only helper; it must not call `_render_query_result`, reset the table
  frame, `_on_query_result_ready`, or `_record_query_history`.
- Replace the lone truncation label placement with a small results-page row containing the existing
  label, the count button, and an inline status/error label. Preserve the existing label object name
  and wording tests.

### Core Data Structures

- `RowCountResult`: frozen domain result in `src/wherewolf/domain/models.py` containing the captured
  request UUID, terminal `ExecutionStatus`, `total_row_count: int | None`, completion time, and
  normalized error fields. Enforce `QueryResult`-style invariants: success requires a non-negative
  total and no error; failure requires error type/message and no total; cancellation has neither
  total nor error.
- `_EditorTabState` gains only transient count status/result metadata needed to restore the correct
  button/label when tabs change. `last_request` remains the base user request.
- `ExecutionRequest`, persisted catalog/history data, and `QueryResult` fields do not change.

### Public Interfaces

- Optional DuckDB adapter capability:
  `count_rows(request: ExecutionRequest) -> RowCountResult`.
- `RowCountController.count(request) -> bool`, `cancel() -> bool`, `shutdown() -> bool`, plus
  `started`, `result_ready`, and cancellation-handle signals following `ExportController` patterns.
- `MainWindow.count_all_rows_button` and `result_count_status_label` are test-addressable widgets.
- No CLI, saved-query, file-format, persistence, or history interface changes.

### Dependency Requirements

None. Reuse DuckDB, PyQt6, `StatementService`, captured parameters/snapshots, and existing domain
types. `pyproject.toml` and `uv.lock` must not change.

### Scope Boundaries

In scope: on-demand count for a truncated DuckDB result, source-staleness rejection, cancellation,
per-tab routing, and existing summary population.

Out of scope: automatic counts on every query, Spark counting, counting multi-statement scripts,
pagination, changing the preview limit, approximate counts, caching counts across executions,
persisting counts, and fixing the known desktop JSON Lines registration defect.

**Slug used throughout this plan:** `count-all-rows`

---

## Orchestration Contract

**Slug:** `count-all-rows`

**Plan file:**

```text
docs/plans/2026-08-22_count-all-rows.md
```

**Implementation branch:**

```text
feat/count-all-rows
```

**Round-complete marker:**

```text
/tmp/wherewolf/count-all-rows_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/count-all-rows_finalized
```

**Review notes:**

```text
docs/review/count-all-rows-review-*.md
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
git checkout -b feat/count-all-rows
```

Commit this plan first:

```bash
git add docs/plans/2026-08-22_count-all-rows.md
git commit -m "docs(plan): add count-all-rows implementation plan"
```

---

## Implementation Tasks

Execute in order with strict RED-GREEN-REFACTOR. Tests must be written and observed failing before
each implementation slice. Use `./run.sh` for project tooling and atomic Conventional Commits.

### 1. Establish the baseline

Run `git status --short` and `./run.sh uv run pytest -q`. Record the exact starting tally in
`docs/agent_conversations/2026-08-22_count-all-rows.json`. Stop on a red baseline or unexpected
workspace modifications.

### 2. RED: specify the DuckDB count capability

Add tests to `tests/test_registry.py` before adapter code:

- a five-row captured query with preview limit two returns total five;
- a filtered query counts only matching rows;
- repeated bound parameters retain order and values;
- a single statement with a trailing semicolon, with/without a trailing line comment, is safely
  wrapped while literal/comment semicolons are untouched;
- `ORDER BY` and inner `LIMIT` retain their query semantics;
- zero-row and exactly-at-preview-limit queries return exact counts when the adapter is called
  directly;
- two executable statements are rejected with a stable message before DuckDB executes the wrapper;
- changed, missing, or differently sized captured sources are rejected before counting; and
- adapter cancellation and close preserve the existing request-scoped lifecycle.

Add `tests/test_models.py` cases proving invalid `RowCountResult` status/count/error combinations
raise rather than entering controller/UI code.

Run the focused names and record their RED failures:

```bash
./run.sh uv run pytest tests/test_registry.py -q --no-cov -k count_rows
```

### 3. GREEN: implement count SQL and fail-closed source checks

Implement the optional method on `_DuckDBAdapter`. Use `StatementService.split_statements()` only
to require exactly one executable statement; build the subquery from that validated
`StatementSpan.text` after removing one final terminator so trailing comments are excluded and
string/comment semicolons remain untouched. Register every captured binding and pass
`request.parameters` to the outer count.

Call the existing source-snapshot comparison before opening/executing. For this feature, any
warning becomes a failed `RowCountResult` containing
`Source changed since query ran; rerun the query` (including unavailable sources), not a warning
attached to a potentially misleading number. Check the fetched row and integer conversion
explicitly. Normalize DuckDB interrupt/cancel state into `CANCELLED`; normalize expected query/count
errors into `FAILED` without raising across the adapter boundary.

Do not populate `total_row_count` during ordinary preview execution and do not change full export.
Run the targeted registry tests and commit:
`feat(execution): count rows for a captured DuckDB request`.

### 4. RED: specify the independent worker/controller lifecycle

Create `tests/test_row_count_controller.py` first. Model the fixtures on
`tests/test_export_controller.py` and cover:

- first submission starts one worker and a concurrent second submission returns `False`;
- the worker publishes its cancellation handle before count work proceeds;
- success, raised failure, and cancellation become terminal `RowCountResult` values carrying the
  original request UUID;
- adapter close runs exactly once on every terminal path;
- stale/mismatched worker signals cannot be mistaken for another request;
- cancel before/after handle publication behaves deterministically; and
- shutdown permits any handle-publication barrier, quits, and waits without leaking a QThread.

Run the new module, record RED, then implement
`src/wherewolf/desktop/row_count_controller.py`. Keep it independent of `QueryController` and
`ExportController`; share concepts, not mutable worker instances. A cancel request received before
the handle signal must set pending cancellation and invoke the handle immediately when published;
the worker's publication barrier must never deadlock.

Run the controller tests and commit:
`feat(results): add isolated row-count controller`.

### 5. RED: specify results-page and per-tab behavior

Write focused `tests/test_main_window.py` cases before integration:

- the count button is visible/enabled only for a successful truncated DuckDB result;
- it is hidden or disabled for Spark, failure, cancellation, no result, non-truncated result, or a
  request with more than one statement;
- activation sends exactly the tab's captured request to the row-count controller and does not call
  `QueryController.execute`;
- while counting, the inline label says `Counting...`, duplicate activation is impossible, and the
  normal grid/frame remains unchanged;
- success replaces only `total_row_count`, produces the existing `showing 2 of 5 rows` summary,
  preserves filter/sort/selection/export state, and adds no history or Messages entry;
- success updates the summary through a path that does not call `result_table_view.set_frame`; use a
  spy to make this preservation contract observable;
- failure/cancellation preserves the preview and reports inline without manufacturing a total;
- a nominally successful total smaller than the captured preview row count is rejected as
  inconsistent/volatile, preserves the preview, and requests a rerun;
- a result for a superseded request or closed tab is ignored;
- a count launched in one tab updates that tab even if another tab is selected, with correct state
  restored when switching back;
- starting a new user query cancels/invalidate the old count before submission; and
- the existing Cancel action and window shutdown include an active row count without regressing
  query/export cancellation priority.

If pagination or another auxiliary controller already exists when this plan executes, preserve its
cancellation/shutdown wiring and add coexistence coverage; this plan must be additive.

Inject a fake controller into `MainWindow` rather than starting real threads in UI routing tests.
Run the selected tests and record RED:

```bash
./run.sh uv run pytest tests/test_main_window.py -q --no-cov \
  -k "count_all_rows or row_count"
```

### 6. GREEN: integrate the count control without result/history pollution

Add optional `row_count_controller` injection to `MainWindow`, construct the real controller by
default, connect its signals, and add it to cancellation/shutdown handling. Keep Run available, but
cancel/invalidate an active count when a new user query starts so the primary workflow wins.

On success, locate the matching `_EditorTabState`, verify `state.last_request.request_id`, and
replace its frozen `last_result` with a copy containing the total. If that editor is current, update
`_last_result`, recompute only the result-summary text/count controls, and leave the table/proxy
model untouched. Do not call the ordinary result renderer. Do not change `last_request`, result
origin, history, Messages, the displayed frame, filter, sort, selection, or scroll position. Derive
button state from current tab state each time a result/tab/status changes rather than maintaining a
second global truth. After success, leave the count control visibly complete and disabled for that
request rather than offering an unnecessary duplicate count.

Before accepting success, require `total_row_count >= state.last_result.preview_row_count`; treat a
smaller total as an inline inconsistent-result failure and leave the stored result untouched.

Run:

```bash
./run.sh uv run pytest tests/test_models.py tests/test_registry.py tests/test_row_count_controller.py \
  tests/test_main_window.py tests/test_export_controller.py tests/test_query_controller.py \
  -q --no-cov
```

Commit: `feat(results): count every row without replacing the preview`.

### 7. Refactor and document

Keep count-specific SQL/lifecycle code out of `MainWindow`; avoid a generic background-task
framework in this feature. Update README Results grid documentation and add an `Unreleased`
changelog entry describing DuckDB-only scope and source-change behavior. Complete the session log
with modified files, tests, exact tallies, decisions, and deferred work.

Commit: `docs(results): document on-demand row counts`.

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

Follow `references/verification-standards.md` from the orchestration-plan-author skill and record
raw results in the session log.

### Automated acceptance

1. Run focused behavior/lifecycle suites:

   ```bash
   ./run.sh uv run pytest tests/test_models.py tests/test_registry.py tests/test_row_count_controller.py \
     tests/test_main_window.py tests/test_query_controller.py tests/test_export_controller.py -q
   ```

2. Run `scripts/orchestration/run-quality-gates`. Any non-zero command, failed/error tally,
   leaked-thread warning, type error, formatting delta, or TDD-gate failure is a failed round.

### Required failure cases and negative control

After the success tests, run the multi-statement, Spark, changed-source, missing-source,
superseded-request, closed-tab, adapter-failure, and cancellation cases. Assert both the visible
failure state and the preserved grid/history state; merely avoiding an exception is insufficient.

Then run a valid truncated DuckDB count after all failure cases and require the exact total and
summary, proving the controller returns to an operable state.

### Mutation proof

Temporarily bypass request-ID matching in the MainWindow completion handler. Run the superseded-
request test and require it to fail because an old count contaminates the new result. Restore the
implementation using a patch stored under `/tmp/wherewolf/count-all-rows/`, rerun that test, the
grid `set_frame` preservation test, and the valid count test, and require all to pass. Do not use a
destructive reset.

### Manual behavior check

Launch via `./run.sh uv run wherewolf`, query a disposable CSV with more rows than the configured
preview limit, activate **Count all rows**, and record the before/after summary, unchanged first-page
cells, unchanged history length, and button state. Modify the CSV after the preview and repeat;
record the inline rerun instruction and absence of a displayed total.

Manual performance measurement on multi-gigabyte files, Spark counting, network filesystems, and
interaction with future pagination are explicitly deferred and must be recorded as unverified.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished count-all-rows
```

This writes:

```text
/tmp/wherewolf/count-all-rows_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer count-all-rows`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/count-all-rows-review-*.md
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
   scripts/orchestration/clear-finished count-all-rows
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
   git add docs/review/count-all-rows-review-*.md
   git commit -m "docs(review): record count-all-rows review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished count-all-rows
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer count-all-rows` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed count-all-rows
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize count-all-rows
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/count-all-rows_finalized
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
scripts/orchestration/finalize count-all-rows
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/count-all-rows_finished
/tmp/wherewolf/count-all-rows_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
