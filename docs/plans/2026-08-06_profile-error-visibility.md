# Plan: Surface profiling failures and progress in the schema panel (profile-error-visibility)

## Context

A user reported that column profiling "does not work on large datasets, even when
initiated by the user". Investigation shows profiling itself **is** working — the
failure is that when it *doesn't* work, nothing tells the user.

### What was measured

Against a genuinely large fixture (20,000,000 rows, 350,869,760 bytes
uncompressed parquet — well over the 268,435,456-byte
`DEFAULT_PROFILE_MAX_BYTES`):

- automatic profiling was correctly skipped at add time, with
  `profile_skipped_reason` set (`main_window.py:754`);
- the manual Profile button bypassed the cap as designed and **succeeded in
  2.0s**, filling every profile column:
  `order_id BIGINT null%=0.00 distinct=24167530 min=0 max=19999999 mean=9999999.5`.

So neither the size gate nor `SUMMARIZE` performance is the defect.

### The actual defect

With profiling forced to fail, the schema panel is indistinguishable from having
done nothing at all:

| | before Profile | after a **failed** Profile |
|---|---|---|
| Null % / Distinct / Min / Max / Mean | blank | still blank |
| status label | `… — Profiling skipped: source exceeds the configured size limit.` | `… — 5 columns` |
| any error shown | — | **none** |

The error is captured correctly — `entry.profile_error` held the raised message —
but it is never rendered. Three separate causes:

1. **The panel never receives the error.** `MainWindow._on_profile_result` calls
   `schema_panel.set_entries(...)` (`main_window.py:833`), not
   `set_profile_result(...)` (`schema_panel.py:118`). `_update_view` only reads
   `_profile_result.error_message` (`schema_panel.py:226`), which therefore stays
   unset, so profile failures render as blank cells.
2. **No progress feedback while profiling runs.** Schema inspection has a
   `"Schema inspection pending..."` state (`schema_panel.py:191`); profiling has
   no equivalent. `ProfileWorker.run()` has no timeout and
   `_DuckDBAdapter.profile_dataset` issues an unbounded
   `SUMMARIZE {alias}` with no row cap or sampling (`registry.py:245`), so on a
   very large source the UI can sit silent for a long time.
3. **The skip notice is cleared on failure**, which actively misleads: after a
   failed profile the panel looks *more* successful than before the click.

### Scope

Fix the visibility problem. Do **not** add sampling, a row cap, or a query
timeout to `SUMMARIZE` — that changes profiling semantics and is not what was
reported. Note it as deferred instead.

### Cache-root prerequisite

`/tmp/wherewolf` is already a symlink to `~/.local/state/wherewolf-cache` and
`scripts/check_cache_budget.sh` (4 GiB ceiling) exists. The cache was pruned to
2,550,042,097 bytes before this plan by deleting the regenerable
`__pycache__` and `pytest-of-beallio` trees, so there is headroom. Run the budget
gate after every task and record the byte count. Do **not** run
`uv sync --extra spark`.

**Slug used throughout this plan:** `profile-error-visibility`

---

## Orchestration Contract

**Slug:** `profile-error-visibility`

**Plan file:**

```text
docs/plans/2026-08-06_profile-error-visibility.md
```

**Implementation branch:**

```text
feat/profile-error-visibility
```

**Round-complete marker:**

```text
/tmp/wherewolf/profile-error-visibility_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/profile-error-visibility_finalized
```

**Review notes:**

```text
docs/review/profile-error-visibility-review-*.md
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
git checkout -b feat/profile-error-visibility
```

Commit this plan first:

```bash
git add docs/plans/2026-08-06_profile-error-visibility.md
git commit -m "docs(plan): add profile-error-visibility implementation plan"
```

---

## Implementation Tasks

Atomic tasks, in order: one behaviour change, its own tests, its own commit. TDD
— failing test first, record the failure, then implement. Run
`scripts/check_cache_budget.sh` after each task and record the byte count.

**Standing rule:** every test here must assert what the *user sees* — the text of
`SchemaPanel._status_label`, or the contents of `_table_widget` cells. A test that
only asserts a field was set on a `CatalogEntry` does not prove the user was told
anything, and that gap is exactly what let this defect ship.

### Task 1 — Show profiling failures in the schema panel

Route the profile result to the panel so its error reaches `_update_view`.

- In `MainWindow._on_profile_result` (`main_window.py:820-833`), pass the
  `ProfileResult` to the panel via `schema_panel.set_profile_result(...)` in
  addition to the existing catalog update, so `_profile_result.error_message`
  (`schema_panel.py:226`) is populated for the entry being displayed.
- Guard against a stale result: if the panel has since switched to a different
  dataset, a late-arriving failure for the previous one must not overwrite the
  current view. Key the result to the entry id.
- The error must be visibly distinct from a schema error. `_update_view`
  currently renders any `error_msg` as `Schema error: ...` and **hides the
  table** (`schema_panel.py:229`). A profiling failure must instead keep the
  column list visible — the schema is still valid — and append a profiling error
  to the status line, e.g.
  `… — Profiling failed: <message>`.

Tests: after a failed `ProfileResult`, `_status_label.text()` contains
`Profiling failed` and the message; the table stays **visible** with its column
rows intact; a successful result shows no error; a failure for a *different*
entry id does not alter the current panel.

Commit: `fix(schema): surface profiling failures in the schema panel`.

### Task 2 — Keep the skip notice until profiling actually succeeds

Today the `Profiling skipped: source exceeds the configured size limit.` notice
is cleared regardless of outcome, so a failed profile looks cleaner than an
un-profiled one.

Clear `profile_skipped_reason` only when a profile is successfully applied. On
failure it must remain, alongside the Task 1 error.

Tests: after a failed profile the status line still contains both
`Profiling skipped` and `Profiling failed`; after a successful profile it
contains neither; the skip reason survives a failure and a subsequent successful
retry clears it.

Commit: `fix(schema): keep the skip notice when profiling fails`.

### Task 3 — Pending state while profiling runs

Profiling currently gives no sign it is working. Mirror the existing
`"Schema inspection pending..."` pattern (`schema_panel.py:191`).

- When a profile worker is queued for the displayed entry, show
  `Profiling…` in the status line and disable the Profile button so it cannot be
  double-queued.
- Clear the pending state and re-enable the button on **every** terminal
  outcome — success and failure alike. A pending state that survives a failure is
  worse than none.

Tests: the status line contains `Profiling` and the button is disabled between
queue and result; after success the pending text is gone and the button is
enabled; after failure the pending text is gone, the button is enabled, and the
Task 1 error is shown; clicking twice in a row queues only one worker.

Commit: `feat(schema): show a pending state while profiling runs`.

### Task 4 — End-to-end test over a real over-cap dataset

The existing coverage
(`test_manual_profile_bypasses_over_limit_auto_profile_gate_and_updates_schema_panel`)
lowers `profile_max_bytes` to 0 against a two-line CSV, so it never runs
`SUMMARIZE` over meaningful data.

Add a test that builds a fixture **larger than the configured cap** and profiles
it for real through the manual path, asserting the panel's cells are populated.

Budget discipline — this is shared-cache sensitive:

- do **not** create a 300 MB fixture. Instead write a modest fixture (target
  roughly 5-20 MB) into pytest's `tmp_path` and set `profile_max_bytes` *below*
  it, so the over-cap branch is exercised with real data at a fraction of the
  cost;
- the fixture must live under `tmp_path` so pytest removes it; assert it does not
  land under the repo;
- record the fixture's actual byte size and the profiling wall time in the
  session log.

Assert on rendered cells, not just on `entry.profile`: the `Null %`,
`Distinct (approx.)`, `Min`, `Max` columns for at least one numeric and one text
column must be non-empty in `_table_widget`.

Commit: `test(schema): profile a real over-cap dataset end to end`.

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

Standards live at
`~/.claude/skills/orchestration-plan-author/references/verification-standards.md`
(not in this repo). Comply; do not restate. Every step must be able to fail.
Report actual output, not conclusions.

### V1 — Cache budget after every task

```bash
scripts/check_cache_budget.sh; echo "exit: $?"
```

Record the byte count after each of tasks 1-4. Starting point is
2,550,042,097 bytes. Do not run `uv sync --extra spark`.

### V2 — The reported symptom, before and after

This is the whole point of the plan, so demonstrate it directly rather than only
through unit tests. With profiling forced to raise (monkeypatch
`_DuckDBAdapter.profile_dataset` to throw), drive a real `MainWindow`, click the
Profile button, and print:

```
status label text  : <...>
table visible      : <...>
row 0 cells        : <...>
profile button enabled: <...>
```

Required after the fix: the status text names the failure, the table is still
visible with its rows, and the button is re-enabled. Record the literal strings.
Before the fix this printed a clean status line and blank cells — if your "after"
output still looks like that, the fix is not working regardless of the suite.

### V3 — Mutation controls

Revert each immediately after recording. Each must turn the named test red; note
the node id and assertion message.

1. Drop the `set_profile_result` call added in Task 1 → the profiling-failure
   status test fails.
2. Make the profiling error render through the `Schema error:` branch that hides
   the table → the "table stays visible" assertion fails.
3. Clear `profile_skipped_reason` unconditionally again → Task 2 test fails.
4. Leave the pending state set after a failure → Task 3 failure-path test fails.
5. Point Task 4's fixture at a file smaller than the cap → the over-cap test
   fails (it must be asserting the cap was actually exceeded, not just that
   profiling ran).

### V4 — Negative control (runs last)

After every mutation is reverted:

```bash
./run.sh uv run pytest
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check .
```

Record pytest's summary line verbatim and all four exit statuses. `ruff format
--check` is the CI form; the local hook runs `ruff format .`, which rewrites
rather than failing.

### V5 — Manual GUI verification (DEFERRED, not performed by the implementer)

Requires a real display. State as deferred; do not claim done.

- The pending text is actually legible during a slow profile rather than flashing
  past.
- A profiling error is readable in the panel at normal dock width and does not
  truncate the useful part of the message.

### Explicitly not verified / out of scope

- **No timeout, row cap, or sampling is added to `SUMMARIZE`**
  (`registry.py:245`). Profiling a very large source can still take a long time;
  this plan makes that state *visible*, it does not make it faster or
  interruptible. A cancel affordance for profiling is a separate piece of work.
- The root cause of any real-world profiling failure remains unknown, because the
  error was never surfaced. This plan makes such failures reportable; it does not
  fix whatever underlying error a specific dataset may trigger.
- Profiling performance is not benchmarked. The measured baseline is 2.0s for
  20M rows / 350 MB parquet on the reviewer's machine, recorded for reference
  only.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished profile-error-visibility
```

This writes:

```text
/tmp/wherewolf/profile-error-visibility_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer profile-error-visibility`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/profile-error-visibility-review-*.md
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
   scripts/orchestration/clear-finished profile-error-visibility
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
   git add docs/review/profile-error-visibility-review-*.md
   git commit -m "docs(review): record profile-error-visibility review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished profile-error-visibility
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer profile-error-visibility` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed profile-error-visibility
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize profile-error-visibility
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/profile-error-visibility_finalized
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
scripts/orchestration/finalize profile-error-visibility
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/profile-error-visibility_finished
/tmp/wherewolf/profile-error-visibility_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
