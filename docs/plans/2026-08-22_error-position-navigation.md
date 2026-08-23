# Plan: Jump to Query Error Position (error-position-navigation)

## Context

### Problem Definition

When a DuckDB query fails, Wherewolf raises the Messages tab and prints the engine error, but the
user must locate the failing token by eye. DuckDB 1.5.4 commonly returns a source excerpt shaped
like `LINE <n>: <text>` followed by a caret line. The application currently discards that location:
`QueryResult` retains only error strings, `MessagesPanel` stores only a severity role, and
`MainWindow._on_run_triggered()` discards the start/end offsets returned by
`SqlEditor.text_to_run()`.

The editor already has a QScintilla squiggle indicator for formatter diagnostics, but its helper is
private, marks only one character, does not move the caret, and is cleared only by a later format
operation. The feature must connect these existing pieces without ever jumping to a guessed token.

### Intended Outcome

For an editor-originated DuckDB query whose executed SQL is one unparameterized DuckDB-dialect
statement, Wherewolf will:

- extract an exact line and column only when DuckDB supplies a parseable `LINE`/caret excerpt;
- map that relative location back into the full editor buffer, including a selected statement that
  begins partway through a line;
- focus the originating tab, move the caret to the token, ensure it is visible, and draw a squiggle;
- make the corresponding Messages item keyboard- and mouse-activatable; and
- invalidate the navigation target and clear the squiggle as soon as that editor's text changes.

Errors without an exact location remain ordinary non-clickable error messages. Translated SQL,
named-parameter rewrites, multi-statement selections, saved-query direct execution, Spark errors,
and errors received after the editor text changed must not offer navigation in this v1.

### Architecture Overview

- Add a pure parser/mapping service in `src/wherewolf/services/execution_diagnostics.py`. It accepts
  DuckDB's error text and returns a `DuckDbErrorLocation | None` containing the relative line,
  column, and exact source excerpt. Before creating a navigation target, compare that excerpt with
  the corresponding executed-fragment line; source mismatch, elision, tab expansion, or ambiguous
  columns must fail closed. The service must not import Qt or depend on an exception class.
- Replace the tuple value in `MainWindow._result_origin_by_request_id` with a small desktop-owned
  request-origin record carrying the editor, result-origin label, original document snapshot, and
  adjusted start offset of the SQL passed to `ExecutionRequestBuilder`. This is transient state,
  not part of `ExecutionRequest` and not persisted.
- Add public `SqlEditor.show_diagnostic(diagnostic, *, move_cursor=True)` and
  `SqlEditor.clear_diagnostics()` methods. The former clamps positions and marks the supplied
  diagnostic span (at least one visible character); when `move_cursor` is true it also moves the
  caret, calls `ensureLineVisible`, and focuses the editor. Formatter diagnostics call it with
  `move_cursor=False`, preserving their current focus/caret behavior. Connect `textChanged` to the
  clearing method.
- Give each `_EditorTabState` an ephemeral UUID. A messages item stores a desktop-only navigation
  payload containing that editor-state UUID, the absolute `SqlDiagnostic`, and the exact document
  snapshot. `MessagesPanel` emits the payload when the item is activated; `MainWindow` resolves the
  UUID, rejects stale snapshots, selects the originating tab, and delegates navigation to the
  editor.
- Keep `QueryResult` and `ExecutionRequest` unchanged. The engine remains responsible only for
  normalized execution results; presentation-layer code derives optional navigation metadata.

### Core Data Structures

- `DuckDbErrorLocation`: required frozen helper dataclass returned by the pure parser, with one-based
  line/column coordinates and the exact source excerpt relative to the executed fragment.
- `_RequestOrigin`: editor reference, result-origin string, editor-state UUID, document snapshot,
  and fragment start offset. It replaces the current `(SqlEditor, str)` tuple.
- `DiagnosticNavigationTarget`: editor-state UUID, absolute `SqlDiagnostic`, and document snapshot.
  Keep this in the desktop layer so domain models do not acquire Qt/editor concepts.

### Public Interfaces

- `parse_duckdb_error_location(message: str) -> DuckDbErrorLocation | None` in the new pure service.
- `SqlEditor.show_diagnostic(diagnostic: SqlDiagnostic, *, move_cursor: bool = True) -> None` and
  `SqlEditor.clear_diagnostics() -> None`.
- `MessagesPanel.add_diagnostic(..., navigation_target=None)` and/or
  `MessagesPanel.show_query_result(..., navigation_target=None)` retain backward-compatible default
  behavior. `MessagesPanel.diagnostic_activated` emits only for an item with a target.
- No command-line, persisted-storage, catalog, engine-protocol, or file-format interface changes.

### Dependency Requirements

None. Use `re`, existing domain models, and existing PyQt6/QScintilla APIs. `pyproject.toml` and
`uv.lock` must not change.

### Scope Boundaries

In scope: exact DuckDB execution locations, selection/current-statement offset mapping, clickable
Messages navigation, stale-target rejection, and editor indicator lifecycle.

Out of scope: heuristic extraction from errors without a caret, sqlglot-to-DuckDB source maps,
parameter rewrite maps, Spark locations, multiple simultaneous diagnostics, changing execution
history, changing formatter output, or fixing the known desktop JSON Lines registration defect.

**Slug used throughout this plan:** `error-position-navigation`

---

## Orchestration Contract

**Slug:** `error-position-navigation`

**Plan file:**

```text
docs/plans/2026-08-22_error-position-navigation.md
```

**Implementation branch:**

```text
feat/error-position-navigation
```

**Round-complete marker:**

```text
/tmp/wherewolf/error-position-navigation_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/error-position-navigation_finalized
```

**Review notes:**

```text
docs/review/error-position-navigation-review-*.md
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
git checkout -b feat/error-position-navigation
```

Commit this plan first:

```bash
git add docs/plans/2026-08-22_error-position-navigation.md
git commit -m "docs(plan): add error-position-navigation implementation plan"
```

---

## Implementation Tasks

Work in order. Follow strict RED-GREEN-REFACTOR: add each behavioral test before its implementation,
run it and record the expected failure, then make the minimum change that turns it green. Use
`./run.sh` for every project command. Keep commits atomic and Conventional Commit formatted.

### 1. Establish the baseline

Run:

```bash
git status --short
./run.sh uv run pytest -q
```

Record the complete pytest pass/fail tally in
`docs/agent_conversations/2026-08-22_error-position-navigation.json`. Stop if the baseline is red
or if files other than this plan are unexpectedly modified; do not normalize unrelated failures.

### 2. RED: specify DuckDB error-location parsing

Create `tests/test_execution_diagnostics.py` before the service. Cover exact real-world strings:

1. A parser error with `LINE 3:   FROM range(3)` and a caret maps to line 3, column 3 and retains the
   exact source excerpt.
2. A binder error whose caret identifies `missing_column` maps to its first character.
3. A catalog error on a later line maps correctly.
4. `syntax error at end of input`, a message without a `LINE` block, a malformed line number, a
   missing caret, a DuckDB-elided long line, and a caret that falls inside DuckDB's `LINE n: ` prefix
   all return `None` or are rejected during exact source-line validation.
5. Multiline messages use the final coherent `LINE`/source/caret triplet without matching unrelated
   prose containing the word `LINE`.

Run the new module and record that collection succeeds and the behavior tests fail because the
service does not exist or is unimplemented:

```bash
./run.sh uv run pytest tests/test_execution_diagnostics.py -q --no-cov
```

### 3. GREEN: implement the pure parser

Add `src/wherewolf/services/execution_diagnostics.py`. Parse only a coherent adjacent
`LINE <positive integer>: <source>` plus caret line. Convert the caret's display offset to a
one-based source column by subtracting the exact prefix width. Return `None` for incomplete,
ambiguous, or out-of-range input and retain the exact source excerpt for later validation. Preserve
the full engine message when converting a trusted location to `SqlDiagnostic`; do not infer an end
span beyond the identified character.

Do not import DuckDB or Qt. Do not inspect localized exception class names. Export the helper from
`wherewolf.services` only if another existing module needs the package-level import.

Run:

```bash
./run.sh uv run pytest tests/test_execution_diagnostics.py -q --no-cov
```

Commit: `feat(editor): parse exact DuckDB error locations`.

### 4. RED: specify editor navigation and stale-indicator behavior

Add focused tests to `tests/test_sql_editor.py` before changing `SqlEditor`:

- `show_diagnostic` moves the cursor to the one-based line/column, focuses the editor, and fills an
  indicator range wider than zero;
- out-of-range line/column values are safely clamped;
- Unicode preceding the target either maps to the exact QScintilla position or safely declines to
  move when index units cannot be proven equivalent;
- changing editor text clears the existing indicator; and
- calling `clear_diagnostics` repeatedly is harmless.

Use QScintilla's indicator query API or a narrowly scoped spy around `fillIndicatorRange`; do not
assert only that the helper returned. Run the named tests and record their pre-implementation
failure:

```bash
./run.sh uv run pytest tests/test_sql_editor.py -q --no-cov -k diagnostic
```

Then expose the two public methods described in Context, make the marker cover the supplied span
or at least the complete token character, and connect `textChanged` once during editor setup.
Retain formatter behavior by calling the public method with `move_cursor=False`.

Commit: `feat(editor): expose reliable diagnostic navigation`.

### 5. RED: specify request-origin mapping and clickable Messages behavior

Write tests first in `tests/test_messages_panel.py` and `tests/test_main_window.py`:

- activating a non-navigable message emits nothing;
- mouse/keyboard activation of a diagnostic item emits exactly its stored navigation payload;
- a same-dialect, parameter-free DuckDB failure maps a caret in the selected/current statement to
  the correct absolute document line and column;
- a statement selected after earlier editor text maps from the fragment into the full buffer;
- activation selects the originating editor tab before moving the caret;
- editing the originating buffer before the result or before activation makes the target stale,
  leaves the cursor unchanged, and never raises;
- translated, parameterized, multi-statement, saved-query-direct, Spark, and positionless failures
  remain visible but non-navigable; and
- a source excerpt that differs from the executed line, contains an unsafe tab expansion, contains
  an unresolvable Unicode-column mismatch, or is DuckDB-elided remains non-navigable; and
- ordinary success/cancellation Messages behavior is unchanged.

Use a synthetic failed `QueryResult` containing a real DuckDB `LINE`/caret string; do not require a
live database for UI mapping tests. Run the focused tests and record the expected failures:

```bash
./run.sh uv run pytest tests/test_messages_panel.py tests/test_main_window.py \
  -q --no-cov -k "diagnostic or error_position or navigation"
```

### 6. GREEN: integrate navigation without changing execution contracts

Implement the transient records and signal flow described in Context. Preserve the start/end
offset returned by `text_to_run()`. Account explicitly for leading whitespace removed by
`ExecutionRequestBuilder.build()` before adding the fragment's offset to the document position.
Use `StatementService.split_statements()` to require one statement and require DuckDB engine,
DuckDB source dialect, `request.original_sql == request.executable_sql`, and no bound parameters
before attaching a navigation target. Compare the parsed source excerpt byte-for-byte/codepoint-
for-codepoint with the executed fragment line before mapping it into the document; withhold
navigation on any mismatch.

On activation, resolve the editor-state UUID, compare the current full document with the stored
snapshot, select the tab, and call `show_diagnostic`. If any condition is false, return without
moving the caret. When a tab closes, no stored payload may keep behaviorally accessing its deleted
editor.

Do not change history records, `ExecutionRequest`, `QueryResult`, query cancellation, or the raw
error-details control.

Run:

```bash
./run.sh uv run pytest tests/test_execution_diagnostics.py tests/test_sql_editor.py \
  tests/test_messages_panel.py tests/test_main_window.py -q --no-cov
```

Commit: `feat(editor): jump from query errors to source SQL`.

### 7. Refactor and document

Remove duplicated coordinate conversions and keep pure parsing outside `MainWindow`. Update README
Desktop workflow/error behavior and add an `Unreleased` changelog entry. Record files modified,
tests added, scope decisions, exact test tallies, and deferred cases in the session log named in
task 1.

Commit: `docs(editor): document query error navigation`.

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

Apply `references/verification-standards.md` from the orchestration-plan-author skill. Record raw
commands, exit codes, and pass/fail tallies in the session log.

### Automated acceptance

1. Run the four focused modules:

   ```bash
   ./run.sh uv run pytest tests/test_execution_diagnostics.py tests/test_sql_editor.py \
     tests/test_messages_panel.py tests/test_main_window.py -q
   ```

   Failure means any non-zero exit or any failed/error tally.

2. Run the full project gates through the generated orchestration command:

   ```bash
   scripts/orchestration/run-quality-gates
   ```

   Failure means a non-zero exit from ruff check, ruff format check, ty, pytest, or TDD
   enforcement. Do not infer success from truncated or piped output.

### Required negative controls

- Re-run the positionless, translated, parameterized, multi-statement, stale-document, and
  non-navigable-message tests after all happy-path tests. Each must assert that the cursor and tab
  remain unchanged and that no navigation signal is emitted.
- Temporarily mutate `parse_duckdb_error_location` so a valid `LINE`/caret block returns `None`.
  Run the valid parser test and the MainWindow navigation test; both must fail for missing
  navigation. Restore the implementation, rerun both tests, and require both to pass. Preserve the
  mutation diff under `/tmp/wherewolf/error-position-navigation/` while restoring; do not use a
  destructive worktree reset.

### Manual behavior check

Run the application through `./run.sh uv run wherewolf`, add a disposable CSV, and execute a
three-line DuckDB query with a misspelled column. Record that the originating tab becomes active,
the caret lands on the misspelling, the token is visible and squiggled, and activating the Messages
item repeats the jump. Edit the SQL and record that the squiggle clears and the old message no
longer moves the caret.

Manual inspection of screen-reader announcements, non-Linux shortcut conventions, translated SQL
source maps, Spark error formats, and parameter source maps is explicitly deferred. Record these
as unverified rather than implying coverage.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished error-position-navigation
```

This writes:

```text
/tmp/wherewolf/error-position-navigation_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer error-position-navigation`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/error-position-navigation-review-*.md
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
   scripts/orchestration/clear-finished error-position-navigation
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
   git add docs/review/error-position-navigation-review-*.md
   git commit -m "docs(review): record error-position-navigation review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished error-position-navigation
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer error-position-navigation` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed error-position-navigation
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize error-position-navigation
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/error-position-navigation_finalized
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
scripts/orchestration/finalize error-position-navigation
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/error-position-navigation_finished
/tmp/wherewolf/error-position-navigation_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
