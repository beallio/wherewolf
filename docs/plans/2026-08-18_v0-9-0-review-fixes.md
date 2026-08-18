# Plan: Fix v0.9.0 Review Findings (v0-9-0-review-fixes)

## Context

### Problem Definition

The v0.9.0 review found thirteen reproducible correctness, data-safety,
resilience, and scalability defects. Parameterized queries preview correctly but
full-result exports omit their bound values; some Edit and Find/Replace actions
continue targeting the editor that existed at window construction; opening a SQL
file can overwrite an unsaved buffer; restored file-backed drafts are falsely
marked clean; and a saved-query result can apply ordering to unrelated editor
text. Saved-query history currently records the positional `?` form instead of
the reusable named-parameter SQL, while `{dataset}` replacement rewrites tokens
inside literals and comments. Catalog refresh does not recover a restored file,
catalog-save failures escape a service listener, successful results are omitted
from history when their origin tab closes, saved-query filtering repeatedly
parses the whole store, and theme changes leave inactive tabs stale.

The intended outcome is that all thirteen review findings have regression tests
and are fixed without changing the supported SQL surface or introducing new
dependencies. Every user-authored SQL buffer must remain recoverable, exports
must execute the same immutable request as preview, result actions must honor
their provenance, catalog failures must remain visible and recoverable, and
multi-tab commands must resolve their target at activation time.

### Architecture Overview

- Keep immutable execution provenance in `ExecutionRequest`: executable SQL and
  positional values drive execution/export, while `original_sql` remains the
  user-facing, rerunnable named-parameter statement used by history.
- Centralize lexical placeholder handling in
  `src/wherewolf/services/query_parameters.py`. Reuse its quote/comment-aware
  scanner for named parameters and `{dataset}` spans rather than applying global
  string replacement.
- Keep document and result provenance in `_EditorTabState` in
  `src/wherewolf/desktop/main_window.py`. Main-window actions and the non-modal
  Find/Replace dialog must look up or be retargeted to the active editor.
- Keep catalog availability transitions in
  `src/wherewolf/services/catalog_service.py`; the window coordinates workers,
  persistence, and status reporting without allowing storage errors to abort
  later service listeners.
- Cache one `SavedQuery` mapping per `SavedQueriesDock.refresh()` so filtering
  and selection remain in-memory until the next explicit mutation/refresh.

### Core Data Structures

- Extend `ExecutionRequestBuilder.build()` with an optional source/original SQL
  argument. Translation still consumes the bound executable statement, but the
  request stores the unbound named-parameter statement in `original_sql`.
- Extend `_EditorTabState` with explicit result provenance and a save baseline
  that can represent an unreadable/unverified file (`str | None`). A direct
  saved-query run is not editor-owned; an ordinary editor run is.
- Add a frozen placeholder-span representation, or a generic internal span
  scanner, for real `{dataset}` occurrences outside supported quotes/comments.
- Add an in-memory `dict[str, SavedQuery]` to `SavedQueriesDock`, rebuilt from a
  single `SavedQueryStore.get_all()` call during each refresh.

### Public Interfaces

- `ExecutionRequestBuilder.build()` gains a backwards-compatible
  `original_sql: str | None = None` parameter; existing callers that omit it
  retain current behavior.
- `FindReplaceDialog` gains `set_editor(editor: SqlEditor)` and all button
  callbacks dereference its current editor when clicked.
- `CatalogService.refresh_availability(entry_id: UUID) -> CatalogEntry` re-stats
  the entry, changes only availability state, notifies listeners only when the
  value changes, returns the current entry, and raises `KeyError` for an unknown
  ID.
- `query_parameters` exports focused dataset-token discovery/binding helpers;
  callers no longer check or replace `{dataset}` directly.
- No file format, command-line, persisted workspace schema, or storage JSON
  contract changes are required.

### Dependency Requirements

No dependency additions or upgrades are expected. Keep `pyproject.toml` and
`uv.lock` unchanged unless a review note proves a dependency change is
unavoidable. Use the existing DuckDB, Polars, PyQt6, and pytest-qt APIs, and run
all project commands through `./run.sh` so caches remain under `/tmp/wherewolf`.

### Scope Boundaries

- Preserve the existing saved-query behavior in which **Run** executes without
  loading SQL into the editor; **Open in New Tab** remains the explicit editing
  action. Applying result ordering to a direct saved-query result must be
  rejected with a clear status message instead of mutating unrelated SQL.
- Do not persist entered parameter values in query history.
- Keep Spark parameter binding unsupported; parameterized full export remains a
  DuckDB behavior. Do not broaden the scanner to dollar-quoted strings,
  backticks, bracket quoting, or nested block comments in this plan.
- Windows 11 native file-dialog and shortcut behavior is deferred to manual
  platform verification; automated behavior must remain platform-independent.
- Do not fold unrelated refactors or release publishing into this branch.

**Slug used throughout this plan:** `v0-9-0-review-fixes`

---

## Orchestration Contract

**Slug:** `v0-9-0-review-fixes`

**Plan file:**

```text
docs/plans/2026-08-18_v0-9-0-review-fixes.md
```

**Implementation branch:**

```text
feat/v0-9-0-review-fixes
```

**Round-complete marker:**

```text
/tmp/wherewolf/v0-9-0-review-fixes_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/v0-9-0-review-fixes_finalized
```

**Review notes:**

```text
docs/review/v0-9-0-review-fixes-review-*.md
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
git checkout -b feat/v0-9-0-review-fixes
```

Commit this plan first:

```bash
git add docs/plans/2026-08-18_v0-9-0-review-fixes.md
git commit -m "docs(plan): add v0-9-0-review-fixes implementation plan"
```

---

## Implementation Tasks

### 1. Establish the baseline and preserve review scope

1. Inspect `AGENTS.md`, `.protocol`, `pyproject.toml`, `uv.lock`, `run.sh`, this
   plan, and the files named below before changing code.
2. Run the full suite through `./run.sh uv run pytest` and record the baseline in
   the session log. Planning observed `604 passed, 7 deselected`; investigate any
   different starting result before implementing.
3. Use strict Red-Green-Refactor for every numbered behavior unit: add the
   regression test, run the narrowest command and capture its expected failure,
   implement the minimum fix, then rerun the focused test before refactoring.
4. Commit each passing unit atomically with Conventional Commits. Do not batch
   unrelated UI, execution, catalog, and documentation work.

### 2. Preserve parameterized execution provenance and full exports

Relevant files:

- `src/wherewolf/services/execution_request_builder.py`
- `src/wherewolf/desktop/main_window.py`
- `src/wherewolf/execution/registry.py`
- `tests/test_execution_request_builder.py`
- `tests/test_full_export.py`
- `tests/test_main_window.py`

Add failing tests first, then implement all of the following:

1. Make `ExecutionRequestBuilder.build()` accept
   `original_sql: str | None = None`. Strip and validate the executable input as
   today, translate that input, and retain the supplied named-parameter SQL in
   `ExecutionRequest.original_sql`. Reject an empty supplied original statement
   with the same validation contract.
2. Refactor editor and saved-query execution through one parameter-prompt/bind
   path. Preserve the SQL after safe dataset binding but before named-parameter
   binding as `original_sql`; pass the positional SQL and ordered tuple of values
   as the executable request. Cancellation must submit nothing.
3. Verify that a parameterized saved query is recorded in history with `:name`,
   not `?`, and that running the history-restored SQL prompts/binds again. Never
   add parameter values to history JSON or status text.
4. In DuckDB `export_full()`, supply `request.parameters` to every statement that
   executes `request.executable_sql`: CSV and Parquet `COPY`, XLSX count, and XLSX
   relation materialization. Preserve the existing streaming path for CSV and
   Parquet and existing cancellation/cleanup semantics.
5. Update the full-export spies to accept optional parameters. Cover repeated
   parameters and prove the emitted CSV, Parquet, and XLSX data contains bound
   values rather than merely asserting that a method was called.

Suggested atomic commit: `fix(execution): preserve parameterized query provenance`

### 3. Bind `{dataset}` only at real SQL token spans

Relevant files:

- `src/wherewolf/services/query_parameters.py`
- `src/wherewolf/desktop/main_window.py`
- `tests/test_query_parameters.py`
- `tests/test_main_window.py`

Add quote/comment boundary tests before implementation. Refactor the existing
single-quote, double-quote, line-comment, and block-comment scanner so focused
helpers can detect and replace only real `{dataset}` spans. MainWindow must use
those helpers both to decide whether to show the dataset picker and to bind the
selected alias via `quote_identifier()`. Cover multiple real tokens, escaped
quotes, and tokens inside strings, quoted identifiers, and comments. A statement
containing only non-code occurrences must neither prompt nor change text.

Suggested atomic commit: `fix(queries): bind dataset tokens lexically`

### 4. Make all edit surfaces follow the active tab

Relevant files:

- `src/wherewolf/desktop/main_window.py`
- `src/wherewolf/desktop/widgets/sql_editor.py`
- `tests/test_main_window.py`
- `tests/test_sql_editor.py`

Add cross-tab failures first, then:

1. Replace startup-editor Undo, Redo, and Toggle Comment menu bindings with
   MainWindow-owned actions that resolve `current_editor` when triggered. Preserve
   existing labels and shortcuts. Leave editor context-menu actions editor-local.
2. Change `FindReplaceDialog` callbacks to dereference `self._editor`, implement
   `set_editor()`, and retarget the existing non-modal dialog on every editor-tab
   change and close. Prove Find Next, Replace Next, and Replace All cannot mutate
   a hidden prior tab.
3. Apply theme previews to every open editor. Snapshot every editor's prior theme
   when Preferences opens, restore each snapshot on rejection, and apply/persist
   the accepted global theme to all existing editors. New tabs must continue to
   start with the persisted global setting.

Suggested atomic commit: `fix(editor): route actions to the active tab`

### 5. Protect SQL buffers and restore honest dirty state

Relevant files:

- `src/wherewolf/desktop/main_window.py`
- `src/wherewolf/services/settings_service.py`
- `tests/test_main_window.py`
- `tests/test_settings_service.py`

Add failing tests for each document-state transition before changing behavior:

1. Opening SQL may reuse the current tab only when it is an untitled, empty,
   pristine buffer. If the current buffer has text or is file-backed, load the
   chosen file into a new tab and leave the old state untouched. Cancellation or
   read failure must not mutate the existing tab or leave an extra tab behind.
2. On workspace restoration, compare a path-backed draft with the file currently
   on disk. Use the disk text as the save baseline when readable so a persisted
   draft or external disk change is correctly dirty. When the file is missing,
   unreadable, or invalid UTF-8, retain the draft and use an unknown baseline so
   the tab is dirty and recoverable.
3. Recompute the active tab's modified state after restoration and every tab
   switch. Preserve existing Save and Save As semantics and tab labels.

Do not add a destructive confirmation dialog; opening beside the existing buffer
is the deterministic no-data-loss behavior for this release.

Suggested atomic commit: `fix(workspace): preserve buffers when opening SQL`

### 6. Enforce result provenance and complete successful history

Relevant files:

- `src/wherewolf/desktop/main_window.py`
- `src/wherewolf/services/order_by_builder.py`
- `tests/test_main_window.py`

Add failing asynchronous/provenance tests first, then:

1. Mark whether each accepted result originated from the editor buffer or from a
   direct saved-query run. Continue associating editor runs with their origin tab.
2. Allow Apply Query Order only when the displayed result belongs to the current
   editor's latest editor-origin request. For a direct saved-query result, a tab
   mismatch, or stale provenance, leave SQL and results unchanged and show a
   status telling the user to open/run the query in an editor first.
3. Record every successful result exactly once before checking whether its origin
   editor still exists. If a tab closes during execution, omit rendering but keep
   the history entry. Failed and cancelled results remain excluded.

Suggested atomic commit: `fix(results): enforce query provenance`

### 7. Recover catalog availability and isolate persistence errors

Relevant files:

- `src/wherewolf/services/catalog_service.py`
- `src/wherewolf/desktop/main_window.py`
- `src/wherewolf/storage/catalog.py`
- `tests/test_catalog_service.py`
- `tests/test_catalog_store.py`
- `tests/test_main_window.py`

Add service and window failures first, then:

1. Implement
   `CatalogService.refresh_availability(entry_id: UUID) -> CatalogEntry`. Re-stat
   the entry and update `unavailable` in either direction, notify listeners only
   on a state change, return the current entry, and raise `KeyError` for an
   unknown ID.
2. Before refresh workers are queued, re-evaluate availability. A file that has
   returned must clear `unavailable` and proceed through schema/profile refresh;
   a file that disappeared must become unavailable and must not launch pointless
   workers.
3. Catch catalog-store write failures inside `_persist_catalog()` so later
   catalog listeners and the UI model still observe the service update. Surface a
   durable status message, leave `_last_persisted_catalog` unchanged, and retry on
   the next catalog notification and once during orderly window close. A later
   successful retry must advance the persisted projection and clear/replace the
   error status naturally.
4. Test a store that fails once: the service and UI model update, the error is
   visible, no success is falsely recorded, and a subsequent mutation/close retry
   writes the latest complete catalog.

Suggested atomic commit: `fix(catalog): recover availability and save failures`

### 8. Make saved-query filtering linear and in-memory

Relevant files:

- `src/wherewolf/desktop/widgets/saved_queries_dock.py`
- `src/wherewolf/storage/saved_queries.py`
- `tests/test_saved_queries_dock.py`

Add an instrumented-store regression test first. Rebuild a private ID-to-record
mapping from exactly one `get_all()` call per `refresh()`. Populate list items and
perform filtering, context-menu enablement, selection, and signal emission from
that snapshot without `get_by_id()` or further disk reads. Refresh after existing
save/rename/delete mutations remains the cache invalidation boundary. Prove that
typing several filter characters over many records performs no additional store
reads and still emits the correct stable-ID record.

Suggested atomic commit: `perf(saved-queries): cache records during filtering`

### 9. Document, audit, and finish

1. Add an `Unreleased` Fixed section to `CHANGELOG.md`; do not rewrite the v0.9.0
   release entry. Update `README.md` only where the visible Open SQL,
   parameterized-history/export, or saved-query ordering behavior is already
   described and would otherwise become inaccurate.
2. Create
   `docs/agent_conversations/2026-08-18_v0-9-0-review-fixes.json` containing the
   date, objective, files modified, tests added, design decisions, deferred
   verification, and final results required by `AGENTS.md`.
3. Confirm `pyproject.toml` and `uv.lock` did not change. Run the complete quality
   and verification sequence below, commit the documentation/session log, and
   leave a clean worktree before marking the round complete.

Suggested atomic commit: `docs(changelog): record v0.9.0 review fixes`

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

Use `references/verification-standards.md` from the
`orchestration-plan-author` skill as the verification contract. Record each
command, exit code, and meaningful output in the session log. A check is not
evidence unless its documented failure symptom could make the implementation
round fail.

### Automated behavior checks

1. Run the focused regression set after all units are green:

   ```bash
   ./run.sh uv run pytest \
     tests/test_execution_request_builder.py \
     tests/test_full_export.py \
     tests/test_query_parameters.py \
     tests/test_main_window.py \
     tests/test_catalog_service.py \
     tests/test_catalog_store.py \
     tests/test_saved_queries_dock.py -q
   ```

   This must exit zero. Any assertion failure demonstrates that at least one
   reviewed behavior is still incorrect.

2. Run the full suite:

   ```bash
   ./run.sh uv run pytest
   ```

   This must exit zero with no unexpected skips or deselections. Record the final
   counts and compare them with the planning baseline (`604 passed, 7
   deselected`); the pass count should grow with the new regressions.

3. Run the project quality gates exactly as required by `AGENTS.md`:

   ```bash
   ./run.sh uv run ruff check . --fix
   ./run.sh uv run ruff format .
   ./run.sh uv run ty check src/
   ./run.sh uv run pytest
   ```

   Each command must exit zero. Ruff output indicates lint/format drift, ty
   diagnostics indicate an invalid interface/type transition, and pytest failures
   indicate behavioral regression. Then run the generated orchestration quality
   gates from this plan before marking the round complete.

### Mandatory negative controls and positive restoration

Perform these only after the real failure-case tests pass. Keep each temporary
mutation uncommitted, use `apply_patch` for both the mutation and its exact
reversal, and confirm `git diff --check` after reversal.

1. Temporarily remove the forwarding of `request.parameters` from one DuckDB
   full-export execution path. Run the named parameterized export regression from
   `tests/test_full_export.py`; it must fail because DuckDB reports missing bound
   values or the exported value is wrong. Reverse the mutation and rerun that
   test; it must pass.
2. Temporarily make the MainWindow Undo or Toggle Comment action capture the
   construction-time editor. Run the cross-tab action regression in
   `tests/test_main_window.py`; it must fail by observing the wrong tab change.
   Reverse the mutation and rerun that test; it must pass.
3. After both reversals, run:

   ```bash
   git diff --check
   ./run.sh uv run pytest tests/test_full_export.py tests/test_main_window.py -q
   ```

   Both commands must exit zero. A remaining diff error or focused test failure
   means the control was not safely restored or the regression fence is weak.

### Manual desktop smoke test

Launch the app through the wrapper with an isolated settings directory:

```bash
./run.sh env XDG_CONFIG_HOME=/tmp/wherewolf/v0-9-0-review-fixes-config uv run wherewolf
```

Then exercise these observable sequences with two editor tabs and a small local
CSV under `/tmp/wherewolf/v0-9-0-review-fixes-fixtures/`:

1. Run a saved query containing `{dataset}` and `:value`, export the full result
   to CSV, and verify the bound row is present. Reopen the history entry and
   verify it shows `:value` and prompts again.
2. Switch tabs while Find/Replace is open; verify Undo, Redo, Toggle Comment,
   Find Next, Replace Next, and Replace All affect only the active tab. Preview a
   theme and cancel Preferences; verify every tab restores its prior appearance.
3. Type an unsaved draft, choose Open SQL, and verify the file opens beside the
   untouched draft. Restart with a path-backed draft that differs from disk and
   verify the restored tab is visibly modified.
4. Run a saved query without opening it, select a result-column ordering action,
   and verify unrelated editor SQL is unchanged with explanatory status. Start
   an editor query, close its tab before completion, and verify its successful
   result still appears once in history.
5. Restore a catalog entry whose file is absent, recreate the file, refresh it,
   and verify its unavailable state clears and schema/profile work resumes.

Record the app command, fixture paths, and observed result for each sequence.
Any overwritten buffer, cross-tab mutation, missing bound export value, stale
availability, or missing/duplicate history entry fails the smoke test.

### Deferred verification

- Native Windows 11 file-dialog, shortcut, and window-modified presentation must
  be verified on a Windows 11 host; no such host is part of this implementation
  environment. Record this as unverified rather than claiming platform coverage.
- Spark parameterized execution/export is intentionally unsupported and is not
  a release criterion for this plan. Existing Spark tests and CI tiers must still
  pass.
- SQL dialect constructs outside the current scanner contract (dollar quotes,
  backticks, bracket identifiers, nested block comments) remain explicitly out
  of scope.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished v0-9-0-review-fixes
```

This writes:

```text
/tmp/wherewolf/v0-9-0-review-fixes_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer v0-9-0-review-fixes`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/v0-9-0-review-fixes-review-*.md
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
   scripts/orchestration/clear-finished v0-9-0-review-fixes
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
   git add docs/review/v0-9-0-review-fixes-review-*.md
   git commit -m "docs(review): record v0-9-0-review-fixes review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished v0-9-0-review-fixes
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer v0-9-0-review-fixes` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed v0-9-0-review-fixes
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize v0-9-0-review-fixes
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/v0-9-0-review-fixes_finalized
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
scripts/orchestration/finalize v0-9-0-review-fixes
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/v0-9-0-review-fixes_finished
/tmp/wherewolf/v0-9-0-review-fixes_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
