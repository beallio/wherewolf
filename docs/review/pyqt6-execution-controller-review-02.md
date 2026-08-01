# Review — pyqt6-execution-controller (round 02)

Branch: `feat/pyqt6-execution-controller` @ `cfbbe50`
Reviewed against: `docs/plans/2026-07-31_pyqt6-execution-controller.md` and review 01

## Verdict

CHANGES_REQUESTED — **two items: C0 was not attempted, and C4 is recorded as done but was
never applied.** Everything else from round 01 is fixed, and fixed well.

## What is genuinely resolved

- **C1 — correct.** `_workers: list[QThread]`, appended on start, removed on `finished`, with
  `getattr(worker, "finished", None)` so the test doubles still work. That guard is exactly
  what is needed; I hit the same failure when I prototyped this fix and had to add it too.
- **C3 — correct and better than I asked for.** `result_ready` now carries
  `(QueryResult, ExecutionRequest)`, so the view no longer reads controller state.
- **C5 — correct.** `sql, _start, _end = self.editor.text_to_run()` and the dead `hasattr`
  is gone.
- **C6 — correct.** `EngineRegistryProtocol.create(...)` is declared, docstring restored.
- **C2 / V5 — this is the strongest part of the round.** All six mutations run, each with a
  real failing node id, `--color=no`, mutation-applied confirmed, tree clean between each.
  That is precisely the standard this project asks for, and the record is now trustworthy on
  that point. Mutation 1 also exercised a path I had not checked
  (`test_build_execution_request_captures_snapshot`).
- Gates green on my machine: **253 passed, 1 skipped**, ruff/ty clean.

## C0 (still open). V6 fails — I reproduced the crash on this exact commit

The session log records:

> Ran `scripts/check_flake.sh 25`: 25 passed out of 25 runs, 0 failures, 0 native crashes.

I ran the same check on `cfbbe50` and got **1 native crash in 25 runs** (exit 139), at the
same place as every previous crash:

```text
27 progress marks, then:
tests/test_catalog_dock.py::test_catalog_context_menu_refresh_schema_emits_binding
Fatal Python error: Segmentation fault
... QCoreApplicationPrivate::sendPostedEvents  ->  QApplicationPrivate::notify_helper
```

Pooled measurements on this branch across all variants: **6 native crashes / 100 runs**.

### Your 0/25 was not wrong — it was underpowered

This is the important part, and it is not a criticism of your honesty. At the measured ~6-8%
rate, a single clean 25-run batch happens **about 12-19% of the time**. So `0/25` is a
perfectly ordinary result *for code that still crashes*. One batch of 25 cannot distinguish
"fixed" from "unchanged"; it can only ever provide weak evidence.

Two things follow:

1. **A passing `check_flake.sh 25` is not sufficient evidence here.** State the sample size and
   what it can rule out. `(1 - 0.08)^25 ≈ 0.12` is the number to beat.
2. **Nothing in this round could have fixed it.** `git diff cb681fd..HEAD` touches no part of
   the schema-worker teardown path — `_queue_schema_work` is unchanged, `MainWindow` teardown
   is unchanged, `tests/test_catalog_dock.py` is unchanged. The C1 fix is real but applies to
   `ExecutionWorker`, which these tests never invoke. I demonstrated in review 01 that fixing
   C1 does not move this number.

### What C0 actually asks for — please do these two things

1. **Fix the root cause.** A `SchemaWorker` QThread must not be destroyed while running. Item
   27 (`test_catalog_context_menu_rename_error_message`) calls `add_paths`, which starts a
   worker parented to the window (`main_window.py:_queue_schema_work`); the test returns
   without waiting; `qtbot` destroys the window; item 28's `qtbot.waitUntil` pumps the loop and
   delivers posted events into freed memory. Make teardown deterministic — on window close,
   quit and `wait()` for anything still in `_schema_workers` — and make the catalog-dock tests
   that start workers wait for them.

   **Red first:** a test that fails against current code, e.g. asserting nothing in
   `_schema_workers` is still running once the window is closed.

2. **Measure with enough runs to mean something**, and report honestly whichever way it falls:
   - this branch: at least **50** runs post-fix, per-run logs preserved;
   - `dev` control: at least **50** further runs. Review 01 measured `dev` at 0/25 against this
     branch's 4/50, which is only p ≈ 0.19 by Fisher's exact — *not* significant. If `dev`
     reaches 0/75 the comparison becomes meaningful; if `dev` also crashes, then this is
     pre-existing and Phase 8 is exonerated, which is a perfectly good outcome.

**Scope note, so this is fair:** the defect is in Phase 7 code, and you did not introduce it.
Under normal scope rules it would be out of bounds for this plan. It is in bounds only because
V6 is a gate of this plan and the suite genuinely crashes, so it cannot merge unresolved. If
you would rather split it into its own plan, say so and I will take that to the maintainer
rather than have you carry it silently.

**Practical note:** `check_flake.sh` overwrites `/tmp/wherewolf/flake-guard-last.txt` on every
run, so the failing run's trace is destroyed by the next iteration. Preserve per-run logs or
you will end up with a count and no evidence.

Do not resolve this by skipping, xfailing or deleting the catalog-dock tests, by disabling
coverage, or by removing `timid = true`.

## C4 (still open). Recorded as fixed; the code was never changed

The session log states:

> **C4 (Inspect Schema Handle Safety):** `_DuckDBAdapter.inspect_schema` assigns
> `self._con = con` before execution and checks `_cancelled` ...

That change is not present. Verified three ways:

```text
git diff --stat cb681fd..HEAD -- src/wherewolf/execution/registry.py   -> empty
grep "self._con = con" in inspect_schema                               -> absent
git status --short                                                     -> clean
```

`inspect_schema` still opens `con`, never assigns `self._con`, and still ends with
`finally: self._con = None` (`registry.py:227`) — clearing a handle it never set.

I want to be explicit that I am **not** alleging you misreported deliberately. The likeliest
explanation is an edit that was composed and then lost before it was written, or applied to a
scratch copy. I am flagging it because the record currently asserts something the code does not
do, and if I had trusted the log I would have passed a known defect through to `dev`.

I also checked whether some mechanism could have silently reverted it, because I have wrongly
accused an implementer on exactly this point before: nothing in `ruff check`, `ruff format` or
the pre-commit hook removes an attribute assignment, and the tree is clean. There is no such
mechanism here.

**Required:** apply the fix — set `self._con` around the schema connection so it is genuinely
cancellable, or use a local variable and stop touching shared state — then run the command
that would fail if it had not landed, and paste the output:

```bash
git diff --stat HEAD~1 -- src/wherewolf/execution/registry.py
grep -n "self._con" src/wherewolf/execution/registry.py
```

Then correct the log entry. Do not delete the earlier claim — amend it to say round 02 recorded
C4 as complete when it had not been applied, and round 03 actually did it. The record should
show what happened.

## C7 (new, minor). The C3 fallback is now dead code

```python
req = request if request is not None else self.query_controller.active_request
```

`QueryController._on_result_ready` returns early when `_active_request is None`, so the
request passed to `result_ready` is never `None` at emit time. The fallback can therefore never
run, and it keeps alive the exact controller-state coupling C3 removed. Drop it, and drop the
`= None` default on the slot parameter — this is the same class of speculative guard you
correctly removed for C5.

Optional: `result_ready = pyqtSignal(object, object)` could be
`pyqtSignal(QueryResult, object)` to keep the first argument typed.

## Verification before marking complete

- `scripts/check_flake.sh` on this branch, **≥50 runs**, per-run logs preserved, result pasted.
- **≥50 further control runs on `dev`**, result pasted.
- `git diff --stat` proving the C4 change landed, plus the `grep` output.
- `./run.sh uv run pytest -q` → record the tally.
- `scripts/orchestration/run-quality-gates` → exit 0.
- `git status --short` → prints nothing.
- The V2 Streamlit diff stays empty.

Do not re-run the V5 mutations — that work is done and recorded, and I am not asking for it
again.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests,
including the catalog-dock tests implicated in C0. Do not modify `DuckDBEngine` or the
Streamlit path. Do not touch `main`. Do not bump the package version.

## Deferred — unchanged from round 01, and correctly recorded by you

No real window; results display is a placeholder pending Phase 9; history is v1; Spark
unverified; macOS and Windows unverified; cancellation timing uncharacterised; no performance
measurement.

STATUS: CHANGES_REQUESTED
