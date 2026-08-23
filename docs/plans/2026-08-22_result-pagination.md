# Plan: Page Through Full Query Results (result-pagination)

## Context

### Problem Definition

The bounded preview protects memory but makes rows beyond the configured limit inaccessible inside
Wherewolf. Users must edit `LIMIT`/`OFFSET` manually or increase the global preview cap, and both
choices disrupt the captured result. `_EditorTabState.last_request` already preserves the exact
engine, translated SQL, catalog, parameters, preview limit, and source snapshots required to fetch
another window safely.

Pagination cannot run through `QueryController`: doing so would replace the base request, add
synthetic SQL to history/Messages, and make each next page wrap the previous page. It also cannot
assume the separate Count All Rows proposal has landed. Page availability must be derived from a
`page_size + 1` probe, while using `QueryResult.total_row_count` only when some independent feature
has populated it.

### Intended Outcome

For a successful truncated, single-statement DuckDB result, show **Previous** and **Next** controls
plus a `Page 1` indicator. Moving pages re-executes the captured query in an isolated worker with
an outer `LIMIT <page size> OFFSET <offset>` and displays only that page. Page size is the captured
`ExecutionRequest.preview_limit`, not a later preference value.

- The first preview is page 1; Previous is disabled and Next follows the original `truncated` flag.
- Later fetches request one extra row to determine `has_next` without a total count.
- If `total_row_count` is already known, show ranges such as `rows 1,001-2,000 of 4,812,331` and use
  it to disable impossible navigation, but do not initiate a count.
- Queries without a top-level `ORDER BY` are allowed but show a persistent warning that page
  membership/order is not stable. A detected top-level order only suppresses that syntactic
  warning; documentation must state that duplicate keys and volatile expressions such as
  `ORDER BY random()` still require the user to supply a unique deterministic order.
- Source mutation, query failure, cancellation, stale completion, or an out-of-range request keeps
  the current page visible and reports an inline error/status. No synthetic query reaches history
  or Messages.
- Preview export exports the currently displayed page; full export continues to use the original
  captured request.

This v1 is DuckDB-only and exactly one executable statement.

### Architecture Overview

- Add pure helpers in `src/wherewolf/services/result_pagination.py` to validate/normalize one
  executable statement, build the outer page query, and detect a top-level `ORDER BY` with sqlglot
  using DuckDB dialect. Nested/CTE ordering does not count as a stable final order. If stability
  analysis fails, return `False`; never block execution solely because the warning cannot be
  proven away.
- Add an optional `_DuckDBAdapter.fetch_page(request, offset, page_size)` capability. It rejects
  changed source snapshots, registers the captured catalog on a fresh connection, binds original
  parameters followed by `page_size + 1` and `offset`, materializes at most one extra row, and
  normalizes success, DuckDB failure, and cancellation into a domain `PageResult`. Do not change
  ordinary preview execution or the shared `ExecutionEngine` protocol.
- Add `src/wherewolf/desktop/page_controller.py`, following the request-scoped lifecycle and
  handle-publication barrier used by `ExportController`: one active worker, cancellation,
  request-ID correlation, terminal result normalization, adapter close, and bounded shutdown.
  Cancellation requested before handle publication is queued and applied immediately when the
  handle arrives; request-ID invalidation remains the final stale-completion fence.
- Extend `_EditorTabState` with transient page index, `has_next`, loading/error state, and stable-
  order flag. `last_request` always remains the base user request. On page success, replace only the
  displayed frozen `QueryResult` fields (`frame`, preview count, truncation/has-next, execution
  time), preserving its optional total count and base request ID.
- Add a compact results-page control row. Derive its state from the current editor tab on every
  result, tab switch, operation transition, and new query. The controller result must be applied to
  the owning tab even when it is not current, and rendered only when that tab becomes/currently is
  active.

### Core Data Structures

- `PageResult` frozen dataclass in `src/wherewolf/domain/models.py`: base request UUID, terminal
  `ExecutionStatus`, `frame`, zero-based offset, page size, `has_next`, execution seconds/completion
  time, and normalized error fields. Enforce `QueryResult`-style invariants: success requires a
  frame and no error; failure requires error type/message and no frame; cancellation has neither
  frame nor error. Offset must be non-negative and page size positive in every status.
- `_EditorTabState` gains `page_index`, `page_has_next`, `page_loading`, `page_error`, and
  `page_has_stable_order` (or one equivalent nested transient page-state dataclass).
- No persisted storage, catalog, `ExecutionRequest`, or `QueryResult` schema changes.

### Public Interfaces

- `build_page_sql(executable_sql: str) -> str` and
  `has_top_level_order_by(executable_sql: str) -> bool` pure service helpers.
- Optional DuckDB adapter capability:
  `fetch_page(request: ExecutionRequest, offset: int, page_size: int) -> PageResult` or equivalent
  engine-layer payload with the same contract.
- `PageController.fetch(request, page_index) -> bool`, `cancel() -> bool`, `shutdown() -> bool`,
  and operation signals.
- Test-addressable `previous_page_button`, `next_page_button`, `page_position_label`, and
  `page_status_label` widgets in `MainWindow`.

### Dependency Requirements

None. Reuse existing sqlglot, DuckDB, Polars, PyQt6, `StatementService`, captured request fields,
and source snapshots. `pyproject.toml` and `uv.lock` must not change.

### Scope Boundaries

In scope: DuckDB offset pagination for captured single statements, order warning, fail-closed source
checks, isolated cancellation/routing, per-tab page state, and optional display of an already-known
total.

Out of scope: Count All Rows implementation, keyset/cursor pagination, caching every visited page,
Spark, multi-statement scripts, changing SQL in the editor, persisting page state across restart,
automatic order injection, filtered-grid pagination, and fixing the known desktop JSON Lines
registration defect.

**Slug used throughout this plan:** `result-pagination`

---

## Orchestration Contract

**Slug:** `result-pagination`

**Plan file:**

```text
docs/plans/2026-08-22_result-pagination.md
```

**Implementation branch:**

```text
feat/result-pagination
```

**Round-complete marker:**

```text
/tmp/wherewolf/result-pagination_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/result-pagination_finalized
```

**Review notes:**

```text
docs/review/result-pagination-review-*.md
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
git checkout -b feat/result-pagination
```

Commit this plan first:

```bash
git add docs/plans/2026-08-22_result-pagination.md
git commit -m "docs(plan): add result-pagination implementation plan"
```

---

## Implementation Tasks

Work in order under strict RED-GREEN-REFACTOR. Observe and record each new test's failure before
implementation. Use `./run.sh` for project tooling and atomic Conventional Commits.

### 1. Establish the baseline

Run `git status --short` and `./run.sh uv run pytest -q`. Record the exact starting tally in
`docs/agent_conversations/2026-08-22_result-pagination.json`. Stop on a red baseline or unexpected
workspace modifications.

### 2. RED: specify safe page-query construction and order analysis

Create `tests/test_result_pagination.py` before its service. Cover:

- a simple query becomes one derived-table query with parameterized `LIMIT ? OFFSET ?` slots;
- one final semicolon and surrounding whitespace are removed, including before a trailing line
  comment, without changing semicolons inside strings/comments;
- empty SQL and two executable statements are rejected;
- top-level `ORDER BY` returns true for plain and `WITH ... SELECT ... ORDER BY` queries;
- `ORDER BY` only inside a CTE/subquery/window expression returns false;
- duplicate-key and volatile top-level orders are classified as syntactically ordered, with tests
  documenting that the helper does not promise semantic uniqueness/determinism;
- parsing failure returns false for stability analysis rather than blocking pagination; and
- existing inner `LIMIT`/`OFFSET` remain inside the subquery so pages range over that result.

Run and record RED:

```bash
./run.sh uv run pytest tests/test_result_pagination.py -q --no-cov
```

Implement `src/wherewolf/services/result_pagination.py` using `StatementService` for one-statement
validation; build from the validated `StatementSpan.text` after removing only its final terminator,
so a trailing comment is excluded without touching semicolons in literals/comments. Use sqlglot for
top-level order inspection. Use a collision-resistant internal alias that is valid even when the
source query exposes a similarly named column; do not interpolate offset/page-size integers into
SQL.

Run the new tests and commit:
`feat(results): build safe page queries and order warnings`.

### 3. RED: specify DuckDB page fetching

Add `fetch_page` cases to `tests/test_registry.py` before adapter code:

- page size two over five ordered rows returns `[1, 2]`, `[3, 4]`, then `[5]` with correct offsets
  and `has_next` values;
- original repeated parameters precede page-size/offset parameters and retain their values;
- returned frames never contain the extra probe row;
- page index/offset and page size reject negative/zero values;
- a trailing-semicolon query, inner limit, wide frame, and zero-row page behave correctly;
- changed or missing captured sources fail before returning a page;
- cancellation is normalized and a connection is closed on every path; and
- multi-statement and unsupported-engine capability paths fail explicitly.

Add `tests/test_models.py` cases proving invalid `PageResult` status/frame/error/offset/page-size
combinations raise before controller/UI code can consume them.

Run the focused tests and record RED:

```bash
./run.sh uv run pytest tests/test_registry.py -q --no-cov -k fetch_page
```

Implement the optional capability on `_DuckDBAdapter`. Fetch `page_size + 1`, construct the visible
frame with `.head(page_size)`, and compute `has_next` from the extra row. Preserve request ID and
capture execution duration. Treat any existing source-snapshot warning as a failed rerun-required
`PageResult` for the same consistency reason as full-result navigation. Normalize DuckDB
interrupt/cancel state into `CANCELLED` and expected query/page errors into `FAILED`; do not raise
them across the adapter boundary.

Commit: `feat(execution): fetch bounded pages for captured queries`.

### 4. RED then GREEN: independent page controller

Create `tests/test_page_controller.py` using the patterns in `tests/test_export_controller.py` and
cover one-active-worker enforcement, handle-before-work ordering, success/failure/cancellation
normalization, mismatched request rejection, adapter close, repeated use after failure, and bounded
shutdown without leaked QThreads. Cover cancellation requested before handle publication: it must
be remembered, applied immediately to the published handle, and release any worker barrier.

Run RED, then implement `src/wherewolf/desktop/page_controller.py`. Calculate offset from checked
non-negative page index and captured positive preview limit; guard overflow/pathological input even
though Python integers do not wrap. Pass normalized adapter `PageResult` values through unchanged;
only unexpected adapter exceptions are converted at the worker boundary. Never invoke
`QueryController` or `ExportController`.

Run the controller suite and commit:
`feat(results): add isolated page controller`.

### 5. RED: specify per-tab controls and rendering

Write focused `tests/test_main_window.py` cases before integration:

- controls appear only for a successful, single-statement DuckDB result with another page; Spark,
  failures, cancellations, non-truncated results, and multi-statement requests do not expose them;
- page 1 has disabled Previous, enabled Next, and uses the captured preview limit;
- activation submits the base request and target page without calling `QueryController.execute`,
  changing `last_request`, or adding history/Messages entries;
- loading disables both buttons but keeps the current grid visible;
- success updates page/range labels, frame, preview export source, and next/previous enablement while
  preserving full export's base request and any pre-existing `total_row_count`;
- no known total still navigates correctly using `has_next` from the extra row;
- no top-level order shows the warning; top-level order hides it;
- a page result for a superseded request or closed tab is ignored;
- background-tab completion updates only its owner and restores correctly when selected;
- source/error/cancellation keeps the old page and reports inline;
- a new user query resets page state and cancels/invalidates an old page operation; and
- changing page clears the page-local selection, local sort notice, and preview-filter text so a
  filter from the prior page cannot silently hide rows on the new one.

Inject a fake controller for UI tests. If Count All Rows or another auxiliary controller is already
present when this plan executes, preserve it and prove pagination does not invoke or require it.
Additive Cancel/shutdown wiring must retain every pre-existing auxiliary controller; do not replace
an existing chain with a pagination-only branch.

Run and record RED:

```bash
./run.sh uv run pytest tests/test_main_window.py -q --no-cov \
  -k "pagination or page_navigation or page_controls"
```

### 6. GREEN: integrate independent per-tab pagination

Add optional page-controller injection and connect operation signals. Reset page fields on every
ordinary query result. Derive visible controls from `_EditorTabState`; do not keep a global page
index. On page completion, correlate the base request UUID and owner tab, update only display/page
fields, and rerender only the current owner.

Render an unknown-total range as `rows <start>-<end> · Page <n>` and a known-total range as
`rows <start>-<end> of <total> · Page <n>`. If an empty page is returned despite a previously true
`has_next`, retain the current page and disable Next with an inline explanation rather than showing
an unexplained blank grid.

Extend Cancel and close handling while preserving any independently added auxiliary operation
controllers and their regression tests. Full export must receive the base `last_request`;
preview/selection export must use the currently displayed page frame.

Run:

```bash
./run.sh uv run pytest tests/test_models.py tests/test_result_pagination.py tests/test_registry.py \
  tests/test_page_controller.py tests/test_main_window.py tests/test_export_integrity.py \
  -q --no-cov
```

Commit: `feat(results): page through a captured DuckDB result`.

### 7. Refactor and document

Keep SQL wrapping and stability analysis out of `MainWindow`. Do not introduce a general operation
framework or modify count behavior. Update README Results grid documentation and add an
`Unreleased` changelog entry covering DuckDB-only scope, captured page size, source consistency,
and the `ORDER BY` warning. Complete the session log with exact tallies, files, decisions, and
deferred work.

Commit: `docs(results): document full-result pagination`.

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

Follow `references/verification-standards.md` from the orchestration-plan-author skill and retain
raw evidence in the session log.

### Automated acceptance

1. Run focused suites:

   ```bash
   ./run.sh uv run pytest tests/test_models.py tests/test_result_pagination.py tests/test_registry.py \
     tests/test_page_controller.py tests/test_main_window.py tests/test_export_integrity.py -q
   ```

2. Run `scripts/orchestration/run-quality-gates`. Treat any non-zero subcommand, failed/error
   tally, leaked-thread warning, formatting delta, type error, or dirty generated cache as failure.

### Required failure cases and negative control

After happy paths, run unordered SQL, duplicate-key/volatile ordering classification,
multi-statement, changed/missing source, empty-next-page,
superseded request, closed tab, adapter failure, and cancellation cases. Assert the current page's
frame and base request remain intact, not merely that the process survives.

Then run an ordered three-page query after all failures and require exact row sequences, page
labels, and enablement transitions `Next -> Previous+Next -> Previous only`.

### Mutation proof

Temporarily force the adapter's page offset to zero. Run the second-page integration test and
require it to fail by returning first-page rows. Restore the implementation from a patch under
`/tmp/wherewolf/result-pagination/`, rerun the three-page sequence, and require it to pass. Do not
use a destructive worktree reset.

### Manual behavior check

Launch through `./run.sh uv run wherewolf`, set preview size to three, and query a disposable
seven-row CSV with `ORDER BY id`. Record exact rows and control states across pages 1, 2, 3 and back
to 1; verify preview export contains the current page while full export contains all seven rows.
Repeat without `ORDER BY` and record the warning. Modify the source after page 1 and record that
Next preserves page 1 and requests a rerun.

Manual performance profiling on very large offsets, Spark, keyset pagination, restart persistence,
and integration with a future Count All Rows implementation is explicitly deferred and must be
recorded as unverified.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished result-pagination
```

This writes:

```text
/tmp/wherewolf/result-pagination_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer result-pagination`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/result-pagination-review-*.md
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
   scripts/orchestration/clear-finished result-pagination
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
   git add docs/review/result-pagination-review-*.md
   git commit -m "docs(review): record result-pagination review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished result-pagination
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer result-pagination` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed result-pagination
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize result-pagination
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/result-pagination_finalized
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
scripts/orchestration/finalize result-pagination
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/result-pagination_finished
/tmp/wherewolf/result-pagination_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
