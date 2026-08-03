# Plan: PyQt6 Desktop Migration - Execution controller and DuckDB slice (Phase 8) (pyqt6-execution-controller)

## Context

Fourth slice of the PyQt6/QScintilla desktop migration. Full design in
`docs/plans/2026-07-30-pyqt6-qscintilla-desktop-migration.md` (the "migration document").
**Read its Sections 14.1-14.6 before starting** — state machine, worker model, DuckDB
lifecycle, execution snapshot, translation rules.

**This plan implements Phase 8 only: the execution controller and the DuckDB vertical
slice.** When done, a real DuckDB query runs end to end in the native app for the first time.

Out of scope (each its own later plan): result grid (9), schema/translation/messages panels
(10), history v2 (11), export (12), Spark (13), Streamlit removal (14), release (15).

**Results display is deliberately minimal.** Phase 9 owns the real grid. Wire results to a
temporary receiver sufficient to prove data arrived — no `QAbstractTableModel`, no sorting,
no clipboard.

Tasks are small and single-purpose. Do not merge them. If a task cannot be completed as
written, stop and say so in the session log rather than working around it.

### What already exists — use it, do not rebuild it

- **`domain/models.py`** — frozen slotted `ExecutionRequest(request_id, engine,
  source_dialect, original_sql, executable_sql, catalog, preview_limit, submitted_at)` and
  `QueryResult(request_id, status, frame, execution_seconds, preview_row_count,
  total_row_count, truncated, completed_at, error_type, error_message, error_detail)`.
  `QueryResult.__post_init__` already enforces that a failed result carries error fields and
  no frame. **Use as-is.**
- **`domain/enums.py`** — `ExecutionStatus` already has `IDLE`, `RUNNING`,
  `CANCELLATION_REQUESTED`, `SUCCEEDED`, `CANCELLED`, `FAILED`: exactly Section 14.1.
- **`execution/registry.py`** + **`base.py`** — `EngineRegistry.create(kind, request_id)`
  returns a request-scoped adapter satisfying `ExecutionEngine` (`execute_preview`,
  `inspect_schema`, `cancellation_handle`, `close`). Spark detection is lazy via
  `importlib.util.find_spec`. **Use the registry; never instantiate engines directly.**
- **`services/catalog_service.py`** — `CatalogService.snapshot()` returns
  `tuple[CatalogBinding, ...]`, already proven to be an independent frozen value. **This is
  what the execution snapshot captures.**
- **`services/statement_service.py`** — quote/comment-aware `find_statement()`. The editor's
  `text_to_run()` returns selection-or-current-statement. Reuse; do not re-parse.
- **`desktop/workers/schema_worker.py`** — an existing `QThread` worker. **Read it first.**
  Its tests record the lifetime lesson: `result_ready` is emitted from inside `run()` before
  the `finally` block, so a test that does not wait for the thread can observe a torn-down
  worker.
- **`desktop/actions.py`** — `build_actions()` returns `DesktopActions`; `run` enabled,
  `cancel` disabled. This plan gives them behavior.
- **`translation/translator.py`** — use `translate_statements()`, never the legacy
  `translate()` (Streamlit-only, returns the first statement only).
- **`storage/history.py`** — `HistoryManager.add_entry(...)` writing v1 JSON. History v2 is
  Phase 11; append through the existing API only.

### Known defects you must NOT fix here

- `execution/duckdb_engine.py` opens one persistent `:memory:` connection in `__init__` and
  caches `_registered_views`. Section 14.3 wants a new connection per execution. Task 4
  addresses this **for the desktop path only**.
- `execution/spark_engine.py` swallows exceptions in `get_schema` and uses `cancelAllJobs()`.
  Phase 13. Do not touch.

### Hard constraint: Streamlit must keep working

`app.py`, `engines.py`, `ui/`, `export/`, `storage/`, `constants.py`, `.streamlit/` are not
modified for behavior. `[project.scripts] wherewolf` still launches Streamlit.

**The trap:** `app.py`/`engines.py` use `DuckDBEngine` as an `@st.cache_resource` singleton
whose persistent connection `tests/test_app_cancel.py` relies on for `interrupt()`. Changing
`DuckDBEngine.__init__` or its connection lifetime breaks Streamlit. Add request-scoped
behavior **alongside** it, via the registry adapter.

Note: a repo-wide `ruff format` may touch these files for formatting reasons (raising the
Python floor already did this once). Formatting churn is acceptable; behavior changes are not.

### Repo mechanics that will fail your commits

- `.git/hooks/pre-commit` runs `ruff check .`, `ruff format .`, `ty check .` (whole repo),
  `pytest`, then `scripts/check_tdd.sh`.
- `check_tdd.sh` requires a **flat** `tests/test_<basename>.py` per staged `src/**/*.py`.
  `desktop/query_controller.py` needs `tests/test_query_controller.py`. Flat names only.
- ruff is on the **0.16 default rule set**; `except Exception` trips `BLE001` — annotate a
  deliberate boundary with `# noqa: BLE001` and a site-specific reason.
- **Python floor is `>=3.14`; CI runs 3.14 only.** `[tool.coverage.run] timid = true` is
  load-bearing — removing it reproduces a native segfault on 3.14. **Do not change it.**
- `scripts/check_flake.sh N` runs the suite N times under coverage. **This phase adds threads
  and Qt signals, the highest-risk area for that crash — Verification requires it.**
- Qt tests are headless; `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`.
- **Register every widget with `qtbot.addWidget`**, and **wait for worker threads to finish**
  before a test returns. Both have caused real crashes here.

### Baseline

`dev` at `f30906c`: **224 passed, 1 skipped**, all gates clean, CI green on 3.14.

**Slug used throughout this plan:** `pyqt6-execution-controller`

---

## Orchestration Contract

**Slug:** `pyqt6-execution-controller`

**Plan file:**

```text
docs/plans/2026-07-31_pyqt6-execution-controller.md
```

**Implementation branch:**

```text
feat/pyqt6-execution-controller
```

**Round-complete marker:**

```text
/tmp/wherewolf/pyqt6-execution-controller_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/pyqt6-execution-controller_finalized
```

**Review notes:**

```text
docs/review/pyqt6-execution-controller-review-*.md
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
# ORCH_LOCAL_ONLY: local trial branch, skipping origin pull
git checkout -b feat/pyqt6-execution-controller
```

Commit this plan first:

```bash
git add docs/plans/2026-07-31_pyqt6-execution-controller.md
git commit -m "docs(plan): add pyqt6-execution-controller implementation plan"
```

---

## Implementation Tasks

**Ten small tasks, one deliverable each, one commit each.** Failing test first, watch it
fail, then implement. Run `./run.sh uv run pytest` after every task. Commit the session log
in Task 1 and append as you go — do not leave it to the end.

Tasks 2-5 are pure logic with **no Qt imports**. Qt appears from Task 6.

### Task 1 — Session log and baseline
Emit the `AGENT_PROTOCOL_HANDSHAKE` (`AGENTS.md` §1). Create **and commit**
`docs/agent_conversations/2026-07-31_pyqt6-execution-controller.md` with the §14 headings.
Run `./run.sh uv sync --all-extras --dev` then `./run.sh uv run pytest -q`; expect
**224 passed, 1 skipped**. Record it and `git rev-parse HEAD`.
Commit: `docs: record execution controller baseline`.

### Task 2 — `ExecutionRequestBuilder`: the immutable snapshot
§14.5. The correctness core — history and export depend on the request being a frozen
point-in-time capture.
**Red** (`tests/test_execution_request_builder.py`): captures original SQL, chosen statement,
source dialect, executable SQL, engine, catalog bindings, preview limit, fresh `request_id`,
`submitted_at`; **mutating `CatalogService` after building does not change the request**
(add and rename entries, assert `catalog` byte-identical); **editing SQL after building does
not change it**; two builds give different `request_id`; `submitted_at` is timezone-aware
(match `history.py`'s `datetime.now().astimezone()`); empty/whitespace statement is rejected
with an actionable error.
**Green**: `services/execution_request_builder.py`. No Qt. Build from `ExecutionRequest` and
`CatalogService.snapshot()`.
Commit: `feat(services): add immutable execution request builder`.

### Task 3 — Translation into `executable_sql`
§14.6. **Red**: same dialect → `executable_sql == original_sql` (no gratuitous rewriting);
differing → translated form with `original_sql` preserved; **a multi-statement selection does
not silently lose statements** (assert which of preserve-or-reject you chose — never "returns
the first"); untranslatable raises `TranslationError` and **no request is produced**.
**Green**: use `translate_statements()`.
Commit: `feat(services): translate SQL into executable form for execution`.

### Task 4 — Request-scoped DuckDB execution via the registry
§14.3. **Do not modify `DuckDBEngine`.**
**Red** (`tests/test_registry.py`, real temp CSV): each `execute_preview()` uses a **fresh**
connection (register an alias, then execute a second request whose catalog omits it, assert
unknown); connection closed on success, error **and** cancellation; **truncation via
limit-plus-one** (`preview_limit=2` over 5 rows → 2 rows, `truncated True`; over exactly 2 →
`False`); `preview_row_count` never presented as `total_row_count`, which stays `None` unless
genuinely computed; SQL error → `status=FAILED`, real `error_message`, `frame is None`;
missing/unreadable file → structured failure, not a crash.
**Green**: extend `_DuckDBAdapter`. Generate internal relation ids so stale views cannot leak.
Close in `finally`.
Commit: `feat(execution): scope DuckDB execution to a single request`.

### Task 5 — Request-specific cancellation
**Red**: `cancellation_handle()` matches the request id; `cancel()` interrupts **only that**
connection (build two adapters, cancel one, assert the other still executes); `cancel()` on a
finished request is safe and returns a truthful value; a cancelled execution yields
`status=CANCELLED` (not `FAILED`) with no frame. Use a deterministic long query or a
controlled fake — **no sleeps**.
**Green**: handle must be callable from another thread without a queued slot on a blocked
event loop (§14.2).
Commit: `feat(execution): add request-specific query cancellation`.

### Task 6 — `ExecutionWorker`
First Qt task. **Red** (`tests/test_execution_worker.py`, `qtbot`): emits a terminal
`QueryResult` exactly once; publishes a thread-safe `CancellationHandle` **before** the engine
call begins; closes request-scoped resources in `finally` on success/error/cancel; **never
touches a Qt widget from the worker thread**; **every test waits for the thread to finish**
before returning.
**Green**: `desktop/workers/execution_worker.py`, following `schema_worker.py`. Emit domain
objects; never pass widgets in.
Commit: `feat(desktop): add background SQL execution worker`.

### Task 7 — `QueryController` state machine
The heart. §14.1. **Red** (`tests/test_query_controller.py`, fake engine for determinism):
IDLE→Run→RUNNING; RUNNING→success→SUCCEEDED→IDLE; RUNNING→error→FAILED→IDLE;
RUNNING→Cancel→**CANCELLATION_REQUESTED** (not straight to CANCELLED);
CANCELLATION_REQUESTED→confirmed→CANCELLED→IDLE; →finished-first→SUCCEEDED→IDLE;
→cancel-failed→FAILED→IDLE; **a second Run while active is refused**; **a terminal signal
whose `request_id` differs is ignored** (submit A, deliver a stale result, assert state and
emitted result untouched); the active request is not cleared until a terminal signal.
**Green**: `desktop/query_controller.py`. Owns state; widgets emit intent and render. No
engine or SQL logic in the controller.
Commit: `feat(desktop): add query execution state machine`.

### Task 8 — Wire Run and Cancel
**Red**: `Run` has `Ctrl+Return`, `Cancel` has `Ctrl+.`, each the **same `QAction` object** in
toolbar and Query menu (assert with `is`); Run disabled while active, re-enabled on terminal;
Cancel enabled **only** in RUNNING/CANCELLATION_REQUESTED; status bar shows engine, state,
elapsed, preview rows, truncation and **never presents a preview count as a total** (§10.3);
Cancel shows "Cancellation requested", not success; Run with an empty editor surfaces an
actionable message and starts nothing.
Commit: `feat(desktop): wire Run and Cancel to the execution controller`.

### Task 9 — End-to-end integration test and history append
**Red** (`tests/test_desktop_duckdb_flow.py`): write a temp CSV; add via `CatalogService`; put
SQL in the editor; trigger Run through the controller; `qtbot.waitSignal` for the terminal
result (**no sleeps**); assert row/column values and populated `execution_seconds`; assert the
GUI thread was not blocked (signal, not polling).
History: appended **only after** a terminal result; written from the **captured request**, not
live UI state (mutate catalog and editor between Run and completion, assert the recorded entry
matches what was submitted); a failed query still records an entry; state explicitly how a
cancelled query is treated.
**Green**: wire through existing `HistoryManager.add_entry`. v2 is Phase 11.
Commit: `feat(desktop): run DuckDB queries end to end from the native app`.

### Task 10 — README and close out the session log
README: `wherewolf-desktop` now executes DuckDB queries with cancellation; state plainly that
results appear in a **minimal placeholder view** and the full grid is next phase. Bump the
README `cacheBuster` per `AGENTS.md` §13.
Session log: files per task, tests added, baseline vs final tallies, deviations with reasons,
and everything not verified.
Commit: `docs: document native DuckDB query execution`.

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

Written to the standard in
`~/.claude/skills/orchestration-plan-author/references/verification-standards.md`. Every step
can fail and says what failure looks like. V5 breaks things deliberately; V6 is the negative
control and must run **after** the tree is restored. Report output, not conclusions.

### V1 — Suite and gates
```bash
set -o pipefail
output=$(./run.sh uv run pytest -q 2>&1); printf '%s\n' "$output" | tail -5
failed=$(printf '%s\n' "$output" | awk '/^FAILED /{print $2}')
[ -n "$failed" ] && { echo "FAIL: regressions:"; printf '%s\n' "$failed"; exit 1; }
passed=$(printf '%s\n' "$output" | grep -oE '[0-9]+ passed' | tail -1 | cut -d' ' -f1)
[ -z "$passed" ] || [ "$passed" -le 224 ] && { echo "FAIL: passed='${passed:-none}', expected >224"; exit 1; }
echo "OK: $passed passed (baseline 224)"
```
The project is **3.14-only** now; there is no second interpreter to test.
Then `scripts/orchestration/run-quality-gates` — must exit 0.

### V2 — Streamlit path behaviourally untouched
```bash
git diff dev..HEAD -- src/wherewolf/app.py src/wherewolf/engines.py src/wherewolf/ui/ \
  src/wherewolf/export/ src/wherewolf/storage/ src/wherewolf/constants.py .streamlit/
```
Formatting-only churn from `ruff format` is acceptable; **any behavioural change is not**.
Inspect the diff, do not just count files. `storage/history.py` may gain a history call only
if Task 9 required it — no other logic changes.
Then run the Streamlit suites, which depend on `DuckDBEngine`'s cached singleton and
`interrupt()`:
```bash
./run.sh uv run pytest -q --no-cov tests/test_app.py tests/test_app_flow.py \
  tests/test_app_cancel.py tests/test_engines.py tests/test_duckdb_engine.py
```
**Failure looks like:** any failure — request-scoped changes leaked into the shared engine.

### V3 — A real query really runs, off the GUI thread
```bash
./run.sh uv run pytest -q --no-cov tests/test_desktop_duckdb_flow.py -v 2>&1 | tail -15
grep -rn "time.sleep\|sleep(" tests/test_desktop_duckdb_flow.py tests/test_execution_worker.py \
  tests/test_query_controller.py || echo "OK: no sleeps"
```
**Failure looks like:** the file missing, tests skipped, a test asserting only that "a result
object was produced" without checking row/column values, or any `sleep`.

### V4 — Cancellation is truthful and request-scoped
```bash
./run.sh uv run pytest -q --no-cov tests/test_query_controller.py tests/test_registry.py -v 2>&1 | tail -20
```
**Failure looks like:** any test asserting Cancel moves straight to `CANCELLED` — that would
mean the UI claims success it cannot know.

### V5 — Mutation checks: prove the new tests bite
**Commit first** — each ends in `git checkout --`. Revert between each; confirm
`git status --short` is clean. Use `--color=no` when grepping for `FAILED`, and **verify the
mutation actually applied** (`git diff --quiet` must be false) before trusting a "no bite".
Both mistakes produced false findings earlier in this project.

1. **Snapshot is not a snapshot** — hold a live reference to `CatalogService.entries` instead
   of `snapshot()`. → snapshot-isolation test must FAIL.
2. **Stale results accepted** — remove the `request_id` guard. → stale-signal test must FAIL.
3. **Cancel claims success** — go straight to `CANCELLED`. → transition test must FAIL.
4. **Concurrency allowed** — remove the one-query-at-a-time guard. → second-Run test must FAIL.
5. **Truncation wrong** — fetch exactly `preview_limit` and hardcode `truncated=False`. →
   truncation test must FAIL.
6. **Connection leaked** — skip `close()` in the adapter's `finally`. → lifecycle test must FAIL.

Record the failing node id for each, then `git checkout -- src/ tests/` and confirm
`git status --short` prints nothing.

### V6 — No native crash regression, then negative control
This phase adds threads and Qt signals — the highest-risk area for the crash whose mitigation
(`timid = true`) is load-bearing on 3.14.
```bash
scripts/check_flake.sh 25
```
**Pass:** `0 native crashes in 25 runs`. **Failure:** any crash, or exit 2 (an ordinary test
failure, i.e. a real regression). Do not shorten the 25 runs.
Then:
```bash
git status --short
./run.sh uv run ruff check . && ./run.sh uv run ruff format --check . && ./run.sh uv run ty check src/
scripts/orchestration/check-review-notes-not-deleted
```
`git status --short` must print nothing.

### Deferred and explicitly NOT verified
- **No real window; no human saw a query run.** All Qt tests are offscreen. That the app stays
  responsive during a long query is **manual, deferred** — say so unless you actually ran
  `wherewolf-desktop` on a display.
- **Results display is a placeholder**; the real grid is Phase 9. Do not describe results as
  complete.
- **History is still v1.** UUID-based v2 with migration is Phase 11.
- **Spark execution unverified** — DuckDB only.
- **macOS and Windows unverified.**
- **Cancellation timing is not guaranteed** — DuckDB's `interrupt()` is best-effort; a query
  may finish before the interrupt lands. The path is tested; real-world timing is not
  characterised.
- **No performance measurement** — the migration document's responsiveness targets were not
  measured; say so rather than implying they were met.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished pyqt6-execution-controller
```

This writes:

```text
/tmp/wherewolf/pyqt6-execution-controller_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer pyqt6-execution-controller`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/pyqt6-execution-controller-review-*.md
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
   scripts/orchestration/clear-finished pyqt6-execution-controller
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
   git add docs/review/pyqt6-execution-controller-review-*.md
   git commit -m "docs(review): record pyqt6-execution-controller review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished pyqt6-execution-controller
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer pyqt6-execution-controller` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed pyqt6-execution-controller
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize pyqt6-execution-controller
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/pyqt6-execution-controller_finalized
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
scripts/orchestration/finalize pyqt6-execution-controller
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/pyqt6-execution-controller_finished
/tmp/wherewolf/pyqt6-execution-controller_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
