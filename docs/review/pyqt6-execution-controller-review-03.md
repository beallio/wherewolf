# Review — pyqt6-execution-controller (round 03)

Branch: `feat/pyqt6-execution-controller` @ `f208a66`
Reviewed against: `docs/plans/2026-07-31_pyqt6-execution-controller.md` and reviews 01–02

## Verdict

APPROVED.

All of C0–C7 are resolved, and C0 is not merely reported fixed — it is **root-caused,
mechanically demonstrated, and independently re-measured**. This is the first crash in this
project's history that has been explained rather than avoided.

## C0 — confirmed fixed, with the counterfactual tested

I did not take the reported numbers on trust. My own measurements on `f208a66`:

| condition | native crashes |
|---|---|
| this branch, pre-fix (rounds 01–02) | **6 / 100** |
| this branch, post-fix — **my independent run** | **0 / 25** |
| this branch, post-fix — pooled with your 50 | **0 / 75** |
| `dev` control, pooled (your 50 + my 25) | **0 / 75** |
| **drain removed from `closeEvent` (mutation)** | **SIGSEGV, exit 139, immediately** |

The last row is the one that matters. Replacing the `_schema_workers` drain in
`MainWindow.closeEvent` with `pass` produces an immediate native segfault in a single targeted
run of `tests/test_main_window.py`. The drain is load-bearing, and
`test_main_window_close_waits_for_running_schema_workers` bites about as hard as a test can.

The arithmetic now supports what was only a hypothesis in review 01:

- pre-fix branch 6/100 vs `dev` 0/75 → Fisher's exact **p ≈ 0.033**. Phase 8 really did raise
  the crash rate, by making `MainWindow.__init__` heavier and shifting a latent race.
- post-fix 0/75 against the 6% pre-fix rate → **p ≈ 0.01**. The fix is not luck.

The mechanism, now settled: a `SchemaWorker` QThread parented to a `MainWindow` was destroyed
while still running; its posted events were later delivered into freed memory by the next
test's event-loop pumping, crashing inside
`QCoreApplicationPrivate::sendPostedEvents` → `notify_helper`.

**Phase 8 did not introduce this defect** — it is Phase 7 code — but it did expose it, and you
fixed it properly rather than tuning it out of sight. Credit for that.

## C4 and C7 — confirmed

- **C4** landed this round: `self._con = con` immediately after `connect()`, a `_cancelled`
  check, interrupt handling, and `self._con = None` in `finally` (`registry.py:214-216`).
  `git diff --stat` confirms 23 insertions to `registry.py`.
- **C4 log correction** — you amended the record to state that round 02 reported it complete
  before it was applied, rather than quietly overwriting it. That is exactly right. The value
  of the session log is that it can be trusted, and it survives a mistake being visible in it.
- **C7** — fallback and `= None` default removed; `result_ready` is now
  `pyqtSignal(QueryResult, object)`.

## Final state

- **254 passed, 1 skipped**; `ruff check`, `ruff format --check`, `ty check src/` clean.
- V2: the Streamlit-path diff against `dev` is still **literally empty**.
- V5: all six mutations recorded with real failing node ids (round 02).
- V6: passes, with the sample size stated and the counterfactual tested.

## Follow-ups — deliberately NOT blocking this merge

Both are cosmetic, and both sit in `MainWindow.closeEvent`, which is the code path I have just
spent 75 runs certifying as crash-free. Changing it now would invalidate that measurement and
require re-running it for no behavioural gain. **Carry these into Phase 9**, which touches
`MainWindow` anyway:

1. `closeEvent` reaches into `self.query_controller._workers` — a private attribute of another
   object. This belongs behind a `QueryController.shutdown()` method that quits and waits for
   its own workers.
2. `if hasattr(self, "query_controller") and self.query_controller is not None:` is the same
   speculative guard class that C5 removed. `query_controller` is assigned unconditionally in
   `__init__`, so both halves are dead.

Also stylistic, not worth a round: `tests/test_catalog_dock.py` now repeats
`qtbot.waitUntil(lambda: not any(w.isRunning() for w in window._schema_workers))` eleven times.
An autouse fixture would express it once. Only worth doing when that file is next edited.

## A hypothesis worth recording — do not act on it here

This defect existed in Phase 7 code throughout the `ci-qt-flake-312` investigation, and its
signature is a QThread teardown race whose outcome is pure timing. **Crash B — the unexplained
3.12-only segfault at ~22% that caused Python 3.12 to be deprecated — may have been this same
defect**, with 3.12 simply losing the race far more often than 3.14.

That is a hypothesis, not a finding. It was never tested, and it is out of scope here. But it
is now cheap to test and would be worth doing before 0.6.0 ships: run the 3.12 leg against this
fix and see whether the 22% rate collapses. If it does, the 3.12 deprecation was a workaround
for a bug that is now actually fixed, and the floor decision could be revisited.

Recording it so it is not lost. It is the maintainer's call whether to chase it.

## Still deferred and unverified — accurate as recorded

No human has seen a query run in a real window; all Qt tests are offscreen. Results display is
a placeholder pending Phase 9. History is still v1. Spark is unverified. macOS and Windows are
unverified. Cancellation timing is best-effort and uncharacterised. No performance measurement
was taken — the migration document's responsiveness targets remain unmeasured.

STATUS: APPROVED
