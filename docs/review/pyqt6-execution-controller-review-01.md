# Review — pyqt6-execution-controller (round 01)

Branch: `feat/pyqt6-execution-controller` @ `fe8305e`
Reviewed against: `docs/plans/2026-07-31_pyqt6-execution-controller.md`

## Verdict

CHANGES_REQUESTED — **V6 fails: the suite segfaults on this branch at ~8%.** Plus one real
worker-lifetime defect, and the verification the plan required was never performed.

Read C0 before anything else, and read it carefully: **the segfault is almost certainly not
your fault, and it is not caused by the defect in C1.** I measured that specifically so you
would not go chasing the wrong thing.

## What you did well — do not undo any of it

- **Ten atomic commits, one per task, in plan order.** Easy to review, easy to bisect.
- **V2 is perfect.** `git diff dev..HEAD` over the Streamlit path is *literally empty*, and
  `test_app.py test_app_flow.py test_app_cancel.py test_engines.py test_duckdb_engine.py`
  pass 15 passed / 1 skipped. `DuckDBEngine` untouched, as instructed.
- **The end-to-end test is real** (`tests/test_desktop_duckdb_flow.py`). Real CSV + real
  Parquet, a real cross join through a real `MainWindow`, triggered via
  `desktop_actions.run.trigger()`, asserting `frame.shape == (4, 3)`, exact column names, the
  status-bar string, and the history entry's catalog contents. Substantive, not a smoke test.
- **No sleeps** in the three new Qt test files. `qtbot.waitSignal` and `worker.wait(5000)` —
  the correct pattern, and it respects the `schema_worker` lifetime lesson from the plan.
- **`total_row_count` stays `None`** rather than being faked from `preview_row_count`, and
  truncation is genuine limit-plus-one. Exactly as Task 4 specified.
- Gates green: `ruff check`, `ruff format --check`, `ty check src/`, **252 passed, 1 skipped**
  (up from 224/1).

I ran two of the six mutations myself and **both bite**:

| mutation | result |
|---|---|
| `is_truncated = False` in `_DuckDBAdapter.execute_preview` | `FAILED tests/test_registry.py::test_duckdb_adapter_truncation_limit_plus_one` |
| drop the `request_id` guard in `_on_result_ready` | `FAILED tests/test_query_controller.py::test_query_controller_ignores_stale_worker_signal` |

The new tests are not vacuous. C2 below is about the missing *record*, not about test quality.

## C0. V6 fails — the suite segfaults at ~8% on this branch

`scripts/check_flake.sh 25` does not pass. Measured on Python 3.14 with `timid = true`:

| condition | native crashes |
|---|---|
| this branch, as submitted | **4 / 50** (2/25 and 2/25, two independent batches) |
| `dev` @ `0a96edf` (control, same machine, same session) | **0 / 25** |
| this branch + a fix for C1 applied | **1 / 25** |

### Where it crashes — this is precise, not approximate

Every captured crash stopped after **exactly 27 progress marks**, i.e. during collection
item 28:

```text
tests/test_catalog_dock.py::test_catalog_context_menu_refresh_schema_emits_binding
```

Same position in all three captured crashes. Signature, identically:

```text
Fatal Python error: Segmentation fault
Current thread ... [pytest] (most recent call first):
  <invalid frame>
... libQt6Core.so.6, at QCoreApplicationPrivate::sendPostedEvents(QObject*, int, QThreadData*)
... libQt6Widgets.so.6, at QApplicationPrivate::notify_helper(QObject*, QEvent*)
```

`sendPostedEvents` delivering into `notify_helper`, with the Python frame corrupted to
`<invalid frame>`, is the signature of **a posted event being delivered to a QObject that has
been freed**. It is C-level memory corruption, not a Python exception.

### Why this is not the `ExecutionWorker` and not C1

The crash is *during* item 28, before item 28's own mark prints — so the object that died came
from an earlier test. Item 27 (`test_catalog_context_menu_rename_error_message`) calls
`window.catalog.add_paths(...)`, which reaches `MainWindow._queue_schema_work` and starts a
**`SchemaWorker` QThread parented to the window** (`main_window.py:218-229`). That test then
ends without waiting for the thread; `qtbot` destroys the window; item 28's
`qtbot.waitUntil(...)` pumps the event loop, and the queued events are delivered into freed
memory.

That is **Phase 7 code**. Your `ExecutionWorker` is not involved — none of these tests execute
a query.

I confirmed C1 is not the cause rather than assuming it. I applied a fix for C1 (hold the
worker until `finished`, mirroring `MainWindow`'s `_schema_workers` pattern) and re-measured:
**1 crash / 25**, at the same item 28 with the same signature. Against an 8% baseline,
P(≤1 in 25) ≈ 0.40 — entirely consistent with no change at all. **Fixing C1 does not fix the
segfault.** Fix C1 anyway, because it is independently wrong, but do not expect it to move
this number.

### What I could NOT establish — do not overstate this in the session log

**I cannot show that Phase 8 caused this.** `dev` measured 0/25 against this branch's 4/50,
but Fisher's exact on that table gives **p ≈ 0.19**. That is not significant, and 25 control
runs are underpowered. The honest position is: *this branch reproduces a segfault at ~8%;
`dev` did not reproduce it in 25 runs; the comparison does not reach significance.*

The plausible mechanism is that Phase 8 made `MainWindow.__init__` heavier — it now builds a
`QueryController` child and a real `HistoryManager` — which shifts the timing of a **latent,
pre-existing teardown race** so this branch loses it more often. That is a hypothesis, and it
must be labelled as one.

### What to do

1. **Extend the control**: `scripts/check_flake.sh 25` on `dev` at least twice more. If `dev`
   reaches 0/75 against this branch's 4/50, the comparison becomes meaningful (p ≈ 0.02). If
   `dev` also crashes, the finding is "pre-existing, exposed here" and Phase 8 is exonerated —
   which is a perfectly good outcome, so measure it honestly either way.
2. **Fix the root cause, which is a real defect regardless of who triggered it**: a
   `SchemaWorker` QThread must not outlive or be destroyed with the window that parents it.
   The tests at items 26–29 start schema workers and return immediately. Make them wait, and
   make `MainWindow` teardown deterministic — on close, quit and `wait()` for anything still
   in `_schema_workers`.
3. **Red first.** A test that fails against current code, e.g. asserting no worker in
   `_schema_workers` is still running once the window is closed.
4. Re-run `scripts/check_flake.sh 25` afterwards and paste the result.

Note for whoever runs this: `check_flake.sh` writes every run to the same
`/tmp/wherewolf/flake-guard-last.txt`, so the failing run's trace is overwritten by the next
run. Preserve per-run logs, or you will get a count with no evidence. That cost me a full
25-run batch.

**Do not** "fix" this by skipping, xfailing or deleting the catalog-dock tests, by disabling
coverage, or by removing `timid = true`.

## Required changes

### C1. The worker thread is dropped while it is still running

Real defect, independently of C0. `QueryController._on_result_ready` clears
`self._active_worker = None` (`query_controller.py:117`) on receipt of `result_ready`. But
`ExecutionWorker` emits `result_ready` from *inside* `run()` (`execution_worker.py:43`),
before its `finally` block and well before the thread exits. The worker is constructed with no
parent (`query_controller.py:35`), so `_active_worker` is the **only** reference keeping it
alive.

Verified, not inferred — instrumenting the controller at the moment the reference is dropped:

```text
RUNNING_WHEN_REFERENCE_DROPPED  = True
FINISHED_WHEN_REFERENCE_DROPPED = False
```

A `QThread` becomes eligible for garbage collection while `run()` is still executing. Today
the query is short and the race is rarely lost; a long query makes it likely.

**The codebase already has the right pattern** — `MainWindow` holds schema workers in a list
and removes them on `worker.finished` (`main_window.py:225-228`). Follow it. Clearing
`_active_request` and `_active_handle` on `result_ready` is fine; only the *worker* reference
must outlive the thread.

One practical note from implementing this myself: your controller tests inject fake workers
that have no `finished` signal, so a bare `worker.finished.connect(...)` raises and breaks
seven tests. Guard it the way the surrounding code already guards `handle_published` and
`result_ready`, or give the fakes a `finished` signal.

### C2. Perform V5 and V6, and record the evidence

The session log (`docs/agent_conversations/2026-07-31_pyqt6-execution-controller.md`) is a
task-by-task narration that ends "with TDD green" ten times. It contains **no verification
evidence whatsoever** — no final tally, no V2 diff result, no mutation node ids, no crash-check
output. V5 and V6 appear not to have been run; V6 would have failed if it had been.

This is the one standard this project does not bend on: *every step must be able to fail, and
the record must show that it could.* "TDD green" describes a process, not a measured outcome.

1. **V5 — run all six mutations**, not just the two I checked, and record the **failing node
   id** for each. Follow the plan's guardrails, which exist because both of these mistakes
   produced false findings earlier in this project:
   - confirm the mutation actually applied (`git diff --quiet` must be **false**) before
     trusting any "no bite";
   - grep with `--color=no`, because pytest's coloured `FAILED` lines defeat a plain grep;
   - revert between each; `git status --short` must print nothing afterwards.

   A mutation that genuinely does not bite is a finding worth having — say so and add the
   missing test.
2. **V6** — see C0.
3. Rewrite the Results section to record measured outcomes: final tally, the empty V2 diff,
   six mutation node ids, and the V6 count.

### C3. Do not reach into the controller's mutable state from the view

`MainWindow._on_query_result_ready` reads `self.query_controller.active_request` to build the
history entry. The controller clears `_active_request = None` at `query_controller.py:115` —
two lines *after* it emits `result_ready` at line 113. This works only because the connection
happens to be direct, so the slot runs synchronously inside `emit()`. Make that connection
queued, or move the clear one statement earlier, and history silently stops being written with
no test failing.

Pass what the view needs through the signal, or emit the request alongside the result. Do not
depend on another object's internal teardown ordering.

### C4. `inspect_schema` clears a connection handle it never set

`_DuckDBAdapter.inspect_schema` has `self._con = None` in its `finally` (`registry.py:227`)
but never assigns `self._con`. So a `cancel()` during schema inspection cannot interrupt it,
and if an execution were ever in flight on the same adapter, the schema path's `finally` would
null out the *execution's* handle — silently turning cancellation into a no-op while still
setting `_cancelled = True`.

Latent today, because `SchemaWorker` creates its own adapter with a fresh uuid
(`schema_worker.py:48`). Fix it anyway: set `self._con` around the schema connection so it is
genuinely cancellable, or use a local and stop touching shared state.

### C5. Remove the speculative guards

```python
raw_sql = self.editor.text_to_run()
sql = raw_sql[0] if isinstance(raw_sql, tuple) else str(raw_sql)   # main_window.py:118
if hasattr(self, "_results_text") and self._results_text is not None:  # main_window.py:156
```

`text_to_run()` is annotated `-> tuple[str, int, int]` (`sql_editor.py:204`) and every return
path returns a 3-tuple, so the `str(raw_sql)` branch is unreachable — and if reached it would
stringify a tuple into nonsense SQL. `_results_text` is assigned unconditionally in the
constructor's own build path (`main_window.py:250`), so the `hasattr` is dead.

AGENTS.md §11 forbids speculative code, and both APIs are in this repository. Unpack the tuple
and drop the `hasattr`.

### C6. Two small things

- `EngineRegistryProtocol(Protocol)` has an empty body (`query_controller.py:15-16`). An empty
  protocol structurally matches *every* object, so it provides no type safety while implying
  it does. Declare `create(...)`, or drop it for the real registry type.
- `src/wherewolf/desktop/workers/__init__.py` lost its module docstring
  (`"""Background workers for the PyQt desktop shell."""`). Restore it.

## Not blocking, but note in the session log

- `_register_view` runs `INSTALL excel; LOAD excel;` on every Excel registration — a
  network-dependent call on a hot path that fails offline. Acceptable for now; state it.
- The status bar hardcodes `Engine: DuckDB` while `active_req.engine` is available. Fine while
  DuckDB is the only wired engine; wrong in Phase 13.
- `run()` carries `# pragma: no cover`. That matches the existing `schema_worker.py` precedent
  and is legitimate — coverage cannot see thread bodies — and your tests do drive the thread
  via `start()`. No change needed; I checked only because the pragma would otherwise hide an
  untested body.

## Things I checked that are fine — do not "fix" them

- `create_view(alias, replace=True)` is **not** an injection vector. Tested with
  `v"; DROP TABLE foo; --` as the alias: DuckDB created a view with that literal name and
  executed nothing.
- The `domain/models.py` `CANCELLED` branch is purely additive and cannot affect Streamlit —
  `app.py` and `ui/results.py` import a *different* `QueryResult`, from `wherewolf.execution`.
- Rebuilding file registration inside `_DuckDBAdapter` rather than delegating to `DuckDBEngine`
  is correct: Task 4 required a fresh connection per execution and forbade touching
  `DuckDBEngine`.

## Verification before marking complete

- `scripts/check_flake.sh 25` on this branch → `0 native crashes in 25 runs`, with per-run logs
  preserved.
- At least 50 further control runs on `dev`, reported honestly whichever way they fall.
- All six V5 mutations, each with its failing node id, `--color=no`, mutation-applied check.
- `./run.sh uv run pytest -q` → record the tally.
- `scripts/orchestration/run-quality-gates` → exit 0.
- `git status --short` → prints nothing.
- The V2 Streamlit diff stays empty.

## Constraints

Do not remove `timid = true` — load-bearing on 3.14. Do not disable coverage. Do not skip,
delete or xfail tests, including the catalog-dock tests implicated in C0. Do not modify
`DuckDBEngine` or the Streamlit path. Do not touch `main`. Do not bump the package version.

## Deferred — state these as unverified

No human has seen a query run in a real window; all Qt tests are offscreen. Results display is
a placeholder pending Phase 9. History is still v1. Spark is unverified. macOS and Windows are
unverified. Cancellation timing is best-effort and uncharacterised. No performance measurement
was taken.

STATUS: CHANGES_REQUESTED
