# Phase 10 — Schema, translation, messages, and full-query ordering

Slug: `pyqt6-schema-translation-messages`
Base branch: `dev`
Target release: 0.6.0 (minor). **Do not bump the version in this phase.**

## Context

Phase 9 delivered the result grid. This phase completes the analytical context around the
preview: what the data looks like (schema), what SQL actually ran (translation), what went
wrong (messages), and how to order the **whole query** rather than just the visible page.

Goal, from the migration document: **schema, translation and errors available without leaving
the main window; full-query ordering explicit and tested.**

### What already exists — use it, do not rebuild it

- **`domain/models.py`** — `SchemaResult(entry_id, columns, error_type, error_message)` and
  `ColumnSchema(name, data_type, nullable)` are already defined and populated. **Use as-is.**
- **`domain/models.py`** — **`SqlDiagnostic(message, severity)` already exists** and is already
  used by `sql_editor.py:191` for parse diagnostics. The messages panel should reuse this type
  rather than inventing a parallel one.
- **`desktop/workers/schema_worker.py`** — a working `QThread` that returns `SchemaResult` via
  the registry. Schema fetching is **done**; this phase displays it.
- **`services/catalog_service.py`** — `update_schema()` already stores results, and
  `catalog_model._schema_status_text()` already renders a terse status in the dock. Extend the
  presentation; do not re-plumb the data.
- **`translation/translator.py`** — `translate_statements(query, from_dialect, to_dialect)`
  returns a tuple preserving **every** statement. `translate()` is the legacy Streamlit path
  that returns only the first statement — **never use it.**
- **`services/execution_request_builder.py:33`** already calls `translate_statements()` to
  build `executable_sql`. The translation panel displays what execution already computes; it
  must not translate a second time by a different route.
- **`services/statement_service.py`** — `split_statements()` and quote/comment-aware
  `find_statement()`. Reuse for statement boundaries; do not re-parse SQL by hand.
- **`desktop/widgets/result_table_view.py`** — the grid. Note it currently exposes **only**
  `insert_header_requested`; it has no sort signal, so local sorting cannot trigger a query
  today. Task 11 makes that a guarded property rather than an accident.
- **`desktop/main_window.py`** — the `_results_text` `QTextEdit` is a **transitional "Messages"
  tab** added in Phase 9 precisely so error visibility was not lost. **This phase owns it.**

### The two kinds of sorting — do not conflate them

This is the central distinction of the phase and the most likely source of a serious bug.

| | what it does | cost |
|---|---|---|
| **Local preview sort** (Phase 9) | reorders the rows already fetched, in the proxy model | free, instant |
| **Full-query ordering** (this phase) | rewrites the SQL with `ORDER BY` and **re-executes** | a real query |

Clicking a column header must **never** re-run the query. Ordering the full result set is an
explicit, deliberate action. A user who sorts a 1000-row preview of a 10-million-row table is
sorting the preview, and the UI must not silently pretend otherwise — nor silently launch an
expensive query.

### Known defects you must NOT fix here

- `execution/spark_engine.py` swallows exceptions in `get_schema`. Phase 13.
- History is still v1. Phase 11.
- `ui/results.py` and `ui/file_browser.py` are the **Streamlit** renderers. Not yours.
  Streamlit removal is Phase 14.

### Hard constraint: Streamlit must keep working

Do not modify `src/wherewolf/app.py`, `engines.py`, `ui/`, `export/`, `storage/`,
`constants.py` or `.streamlit/`. Formatting-only churn from `ruff format` is acceptable;
behavioural change is not.

### Python floor: 3.12 AND 3.14

`requires-python = ">=3.12"` was restored after the segfault that caused the 3.12 deprecation
was root-caused and fixed (`docs/review/crash-b-probe-finding.md`). CI tests **both** legs.

- **No PEP 758 unparenthesized `except`** — `except OSError, ValueError:` is a SyntaxError on
  3.12. Write `except (OSError, ValueError):`.
- No 3.13+/3.14-only typing constructs or stdlib APIs.
- `ruff` targets the declared floor, so `ruff check --fix` and `ruff format` keep you honest.
  **Let the tools drive rather than hand-writing modern syntax.**

Practical warning: `./run.sh uv run --python 3.12 ...` re-syncs the **shared**
`UV_PROJECT_ENVIRONMENT` at `/tmp/wherewolf/.venv` to 3.12. Afterwards run
`./run.sh uv sync --all-extras --dev --python 3.14`, or every later measurement is on the wrong
interpreter.

### The crash history you must respect

Phase 8 root-caused a native segfault: `SchemaWorker` QThreads destroyed while still running,
with posted events delivered into freed memory (`sendPostedEvents` → `notify_helper`).
`MainWindow.closeEvent` drains schema workers and calls `QueryController.shutdown()`.

This phase adds more panels and touches the schema worker path directly. **Any QObject you
parent to a transient window, and any thread you start, must not outlive its parent.** If you
touch `closeEvent` or worker lifetime, V10 is mandatory and must be re-run afterwards.

`timid = true` in `pyproject.toml` is load-bearing on 3.14. **Do not remove it.**

### Repo mechanics that will fail your commits

- `scripts/check_tdd.sh` requires a **flat** `tests/test_<basename>.py` per staged
  `src/**/*.py`. A new `src/wherewolf/desktop/widgets/schema_panel.py` needs
  `tests/test_schema_panel.py` — not a nested path.
- The pre-commit hook runs `ruff check`, `ruff format`, `ty check`, `pytest` and
  `check_tdd.sh`, and does `git add -u`, sweeping modified tracked files into your commit.
  Stage deliberately.
- Caches live under `/tmp/wherewolf`. Run project commands through `./run.sh`.
- Commit messages must NOT contain `Co-Authored-By:` or `Claude-Session:` trailers.

### Recording rule — read this before writing the session log

Across Phases 8 and 9 the implementation was consistently correct and the **session log** was
wrong three times: a review item recorded as fixed when the file had zero diff, a tally of
"295 passed" when the real figure was 276, and two mutation entries citing tests that do not
fail under those mutations.

**"Not measured" is a complete and acceptable answer.** If you did not run something, say so.
A plausible-looking number that was never observed is the one thing the record cannot absorb,
because the entire value of the log is that someone can re-run it and get the same answer.

After any change you report, **run the command that would fail if it had not landed, and paste
that output.** Report measured values, never adjectives like "all green".

### Baseline

`dev` @ `7c6ac67`: **277 passed, 1 skipped** on both 3.12 and 3.14; ruff/ty clean; CI green on
`lint`, `test (3.12)`, `test (3.14)`. Record your own baseline in Task 1.

## Orchestration Contract

**Slug:** `pyqt6-schema-translation-messages`

**Plan file:**

```text
docs/plans/2026-08-01_pyqt6-schema-translation-messages.md
```

**Implementation branch:**

```text
feat/pyqt6-schema-translation-messages
```

**Round-complete marker:**

```text
/tmp/wherewolf/pyqt6-schema-translation-messages_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/pyqt6-schema-translation-messages_finalized
```

**Review notes:**

```text
docs/review/pyqt6-schema-translation-messages-review-*.md
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
# ORCH_LOCAL_ONLY: local trial branch, skipping origin pull
git checkout -b feat/pyqt6-schema-translation-messages
```

Commit this plan first:

```bash
git add docs/plans/2026-08-01_pyqt6-schema-translation-messages.md
git commit -m "docs(plan): add pyqt6-schema-translation-messages implementation plan"
```

---

## Implementation Tasks

Each task is one commit, Red before Green. Tasks 2, 5, 6, 9 are **pure functions or Qt-free** —
land the logic testable without a GUI before building widgets on top.

### Task 1 — Session log and baseline
Create `docs/agent_conversations/2026-08-01_pyqt6-schema-translation-messages.md` with the
baseline commit and the measured tally on **both** interpreters. No source changes.
Commit: `docs: record schema translation messages baseline`.

### Task 2 — Identifier quoting rules (Qt-free)
**Red** (`tests/test_identifier_quoting.py`): a plain identifier is inserted bare; one needing
quotes (spaces, mixed case, reserved word, leading digit) is quoted; an embedded quote is
escaped per a **stated** rule. Assert exact strings.
**Green**: `src/wherewolf/services/identifier_quoting.py`.
Commit: `feat(services): add SQL identifier quoting rules`.

### Task 3 — Schema panel: columns and types
**Red** (`tests/test_schema_panel.py`, `qtbot`): selecting a catalog entry lists its real column
names and data types; an entry with no schema yet shows a pending state, not an empty table
indistinguishable from "no columns".
**Green**: `src/wherewolf/desktop/widgets/schema_panel.py`, fed from `CatalogEntry.schema`.
Commit: `feat(desktop): add schema panel`.

### Task 4 — Schema error display
**Red**: a `SchemaResult` carrying `error_type`/`error_message` surfaces the real message, and
the panel does not present a failed inspection as an empty schema.
**Green**: error state in the panel.
Commit: `feat(desktop): surface schema inspection errors`.

### Task 5 — Insert schema column into the editor
**Red**: inserting a column emits the correctly quoted identifier from Task 2 at the cursor;
inserting from a multi-column selection produces a comma-separated list in **display order**.
**Green**: wire the panel to the editor via a signal — the panel must not import the editor.
Commit: `feat(desktop): insert schema columns into the editor`.

### Task 6 — Translation view model (Qt-free)
**Red** (`tests/test_translation_view_model.py`): given source SQL and a dialect pair, produce
the translated text for display; **no statement is lost** — N statements in, N statements out,
asserted with a real multi-statement query; an untranslatable construct produces a
`SqlDiagnostic` with a real message rather than raising or silently dropping the statement.
**Green**: `src/wherewolf/services/translation_view_model.py` using `translate_statements()`.
**Never** call the legacy `translate()`.
Commit: `feat(services): add translation view model`.

### Task 7 — Translation panel
**Red** (`tests/test_translation_panel.py`, `qtbot`): the panel shows the translated SQL for the
current statement; it shows the **same** text execution would run; diagnostics from Task 6 are
visible.
**Green**: `src/wherewolf/desktop/widgets/translation_panel.py`.
Commit: `feat(desktop): add translated SQL panel`.

### Task 8 — Messages panel, replacing the transitional `QTextEdit`
**Red** (`tests/test_messages_panel.py`, `qtbot`): messages display **severity** and detail;
an execution error shows its `error_type` and `error_message`; a cancellation shows a distinct
message; severities are visually distinguishable (assert the role/state, not a colour).
**Green**: `src/wherewolf/desktop/widgets/messages_panel.py` reusing `SqlDiagnostic`. **Remove
`_results_text`** and update `MainWindow` to route messages here. Keep every message path Phase
8 and 9 established — failed and cancelled results must still surface.
Commit: `feat(desktop): add messages panel and retire the placeholder text view`.

### Task 9 — Full-query ORDER BY generation (Qt-free)
**Red** (`tests/test_order_by_builder.py`): wrapping a simple `SELECT` produces exact SQL with
`ORDER BY <quoted col> ASC|DESC`; a query that **already** has `ORDER BY` is handled per a
**stated** rule (replace or wrap — state which and test it); a query with `LIMIT` is not
silently reordered into a different result; identifiers are quoted via Task 2. Assert exact
SQL strings.
**Green**: `src/wherewolf/services/order_by_builder.py`. Use `statement_service` for statement
boundaries; do not hand-parse.
Commit: `feat(services): add full-query ORDER BY builder`.

### Task 10 — Apply Ascending/Descending Order to Query
**Red**: the action builds the ordered SQL from Task 9 and submits **one** new execution
through `QueryController`; the editor text is updated to the ordered query (or the ordering is
visibly represented — state which); the action is disabled when no result is present.
**Green**: wire the header context menu and/or a toolbar action.
Commit: `feat(desktop): add apply-order-to-query action`.

### Task 11 — Guard: local sort must NOT re-run the query
**Red**: a test that counts executions — sort the grid by clicking a header, cycle
ascending/descending/clear, and assert the execution count is **unchanged**. This must fail if
someone later wires local sort to re-execution.
**Green**: no production change is expected; if one is needed, that is a real finding — record
it.
Commit: `test(desktop): guard against re-running the query on local sort`.

### Task 12 — Result request details and metrics
**Red**: the UI surfaces the request's engine, elapsed time, preview row count and truncation
state; a truncated result says so explicitly.
**Green**: extend the details/metrics surface. Reuse `QueryResult`'s existing fields; do not
recompute.
Commit: `feat(desktop): show result request details and metrics`.

### Task 13 — README and close out
Document the panels, the ordering action, and **explicitly document the difference between
local preview sort and full-query ordering** — that distinction is user-facing. Bump the README
`cacheBuster` per AGENTS.md §13. Finalise the session log with measured results.
Commit: `docs: document schema translation messages and close out session log`.

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
**Failure looks like:** running only 3.14. A 3.14-only construct is a hard `SyntaxError` on
3.12 — the suite cannot even import.

### V2 — Streamlit path behaviourally untouched
```bash
git diff dev..HEAD -- src/wherewolf/app.py src/wherewolf/engines.py src/wherewolf/ui/ \
  src/wherewolf/export/ src/wherewolf/storage/ src/wherewolf/constants.py .streamlit/
./run.sh uv run pytest -q --no-cov tests/test_app.py tests/test_app_flow.py \
  tests/test_app_cancel.py tests/test_engines.py tests/test_duckdb_engine.py
```

### V3 — Schema is real
The panel test must assert **actual column names and types** from a real file, and that a
schema **error** is distinguishable from an empty schema. **Failure looks like:** asserting
only `rowCount() > 0`.

### V4 — No statement loss in translation
A multi-statement query must produce the same number of statements after translation, asserted
on a real example. **Failure looks like:** a test with a single statement, which cannot detect
the legacy `translate()` behaviour.

### V5 — ORDER BY SQL is exact
Assert exact generated SQL strings, including quoting and the already-has-`ORDER BY` rule.
**Failure looks like:** asserting `"ORDER BY" in sql`.

### V6 — Local sort does not re-execute (hard requirement)
```bash
./run.sh uv run pytest -q --no-cov tests/test_result_table_view.py -v
```
The Task 11 test must count executions and assert **zero** new ones across a full
ascending/descending/clear cycle. **Failure looks like:** asserting a UI state instead of an
execution count.

### V7 — Messages carry severity
Assert severity is represented and distinguishable, and that failed and cancelled results still
surface after `_results_text` is removed. **Failure looks like:** the removal silently dropping
Phase 8's error paths.

### V8 — Mutation checks: prove the new tests bite
**Commit first.** Verify each mutation applied (`git diff --quiet` must be **false**) before
trusting a "no bite"; grep with `--color=no`; revert between each; `git status --short` clean
afterwards. **Record the failing node id for each — the id you actually observed.**

1. Quote nothing in `identifier_quoting` → the quoting test must FAIL.
2. Use legacy `translate()` instead of `translate_statements()` → the statement-loss test must
   FAIL.
3. Drop the `ORDER BY` direction (always ascending) → the descending test must FAIL.
4. Ignore an existing `ORDER BY` when wrapping → that test must FAIL.
5. Present a schema error as an empty schema → the schema-error test must FAIL.
6. Make local sort trigger an execution → the Task 11 guard must FAIL.

Mutation 6 is the most important in this phase — it is the regression this design exists to
prevent.

### V9 — No 3.14-only syntax
```bash
grep -rn "except [A-Za-z_.]*, [A-Za-z_.]*:" src/ tests/ || echo "OK: none"
```

### V10 — No native crash regression (hard gate)
```bash
scripts/check_flake.sh 25    # run TWICE; 50 runs total
```
**Pass:** 0 native crashes in 50. **Failure:** any crash, or exit 2.

Two things learned the hard way: `check_flake.sh` overwrites
`/tmp/wherewolf/flake-guard-last.txt` every run, so **preserve per-run logs** or you report a
count with no evidence. And a single clean batch of 25 proves little — at a 6% rate, `0/25`
happens ~21% of the time for code that still crashes. That is why this asks for 50.

If a crash appears: capture the trace, count progress marks before `Fatal Python error`, and
map to `pytest --collect-only -q`. `sendPostedEvents` crashes are **delayed** — the crash site
names the test that pumped the event loop, not the one that leaked the object.

### Deferred and explicitly NOT verified
- **No human has seen these panels.** All Qt tests are offscreen. Say so.
- **No performance measurement.** Do not imply the migration document's responsiveness targets
  were met.
- History v2 is Phase 11, export is Phase 12, Spark is Phase 13, Streamlit removal is Phase 14.
- macOS and Windows unverified.
- Spark schema and translation paths remain unverified — DuckDB only.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests. Do
not use the legacy `Translator.translate()`. Do not modify the Streamlit path or
`DuckDBEngine`. Do not touch `main`. Do not bump the package version — 0.6.0 belongs to the
final cutover.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished pyqt6-schema-translation-messages
```

This writes:

```text
/tmp/wherewolf/pyqt6-schema-translation-messages_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer pyqt6-schema-translation-messages`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/pyqt6-schema-translation-messages-review-*.md
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
   scripts/orchestration/clear-finished pyqt6-schema-translation-messages
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
   git add docs/review/pyqt6-schema-translation-messages-review-*.md
   git commit -m "docs(review): record pyqt6-schema-translation-messages review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished pyqt6-schema-translation-messages
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer pyqt6-schema-translation-messages` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed pyqt6-schema-translation-messages
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize pyqt6-schema-translation-messages
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/pyqt6-schema-translation-messages_finalized
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
scripts/orchestration/finalize pyqt6-schema-translation-messages
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/pyqt6-schema-translation-messages_finished
/tmp/wherewolf/pyqt6-schema-translation-messages_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
