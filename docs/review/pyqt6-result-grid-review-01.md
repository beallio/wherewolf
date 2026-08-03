# Review — pyqt6-result-grid (round 01)

Branch: `feat/pyqt6-result-grid` @ `47cb9ee`
Reviewed against: `docs/plans/2026-08-01_pyqt6-result-grid.md`

## Verdict

CHANGES_REQUESTED — **the implementation is good and I found no correctness defects.** What is
missing is the verification record: V7 was not run, and the session log states a test tally
that is wrong. This is a light, precisely-scoped round. Do not touch the implementation.

## What you did well — do not undo any of it

- **Thirteen atomic commits in plan order.** Easy to review and bisect.
- **V4 is exactly right.** `[2, 10, 1] → [1, 2, 10]` is asserted, which is the whole reason
  that task existed — a lexicographic sort would give `[1, 10, 2]`. Descending asserted too,
  and null ordering is stated as a rule (nulls last in both directions) and tested **both
  ways**, which is more than the plan strictly required.
- **V5 is exemplary.** Exact string assertions, including the hard cases: visual column order
  (`"b\ta\nx\t1\ny\t2"`), discontiguous selection, quoted headers, and values containing tabs
  and newlines. No "clipboard is non-empty" hand-waving anywhere.
- **V3 is real.** The wiring tests assert typed cell values through `UserRole` (`== 100`), row
  and column counts, the status-bar string, the error text, and that a cancelled result clears
  the grid.
- **Task 12 done properly.** `QueryController.shutdown()` added and called from `closeEvent`;
  the private `_workers` reach-through and the dead `hasattr` guard are both gone.
- **The autouse fixture is well built.** Using `QApplication.topLevelWidgets()` to find live
  windows is the right approach — I tried monkeypatching `MainWindow.__init__` for the same
  purpose while investigating Phase 8 and it destabilised the run. Yours does not.
- **`ResultTableView(self)` is parented to the window**, which matters given this project's
  crash history.

## Measurements I ran myself

| check | result |
|---|---|
| suite on **3.14** | 276 passed, 1 skipped |
| suite on **3.12** | 276 passed, 1 skipped — identical |
| `run-quality-gates` | pass |
| **V8** `check_flake.sh` 25 + 25 | **0 native crashes / 50** |
| V7 mutation 1 (sort on `DisplayRole`) | 3 tests FAILED |
| V7 mutation 3 (ignore visual column order) | 1 test FAILED |

**V8 is satisfied.** You do not need to re-run it unless you change source code in this round.

The 3.12 leg matching 3.14 exactly is the notable result — the restored floor holds, and no
PEP 758 syntax crept in.

## Required changes

### C1. The session log states a tally that is wrong

The log says:

> Total Tests Run: 295 passed, 1 skipped.

The actual figure is **276 passed, 1 skipped**.

I checked whether the two refactor commits that landed after the log (`1d3a144`, `47cb9ee`)
had removed tests, rather than assuming the number was invented: `pytest --collect-only`
reports **277 collected at both** that commit and HEAD. Nothing was removed. The number is
simply incorrect.

Correct it, and add the 3.12 tally, which the log does not record at all — it claims
"100% pass across Python 3.14 and Python 3.12" without a figure for either. Record measured
numbers, not adjectives.

### C2. Run the four remaining V7 mutations and record all six

V7 requires six mutations with failing node ids. The log records none. I ran two of them and
both bite, so I have no reason to doubt the tests — but two is not six, and the four I did not
run are the ones most likely to expose a weak assertion.

**Do not re-run mutations 1 and 3** — I have done those and the results are in the table above.
Run these four:

2. Reverse the null-ordering rule → the null-ordering test must FAIL.
4. Include hidden columns in copy → the hidden-column test must FAIL.
5. Off-by-one in the filtered→source row mapping → the mapping test must FAIL.
6. Drop the third-click sort reset → the restore-original-order test must FAIL.

Follow the plan's guardrails, which exist because both mistakes have produced false findings in
this project: confirm the mutation applied (`git diff --quiet` must be **false**) before
trusting a "no bite", grep with `--color=no`, revert between each, and confirm
`git status --short` prints nothing afterwards.

If one genuinely does not bite, say so and add the missing test — that is a useful finding, not
a failure.

### C3. Answer a scope question: the "Messages" tab

Task 11 said to replace the `QTextEdit` placeholder. You kept it and added it as a second tab:

```python
results.addTab(self.result_table_view, "Results")
results.addTab(self._results_text, "Messages")
```

A messages panel is **Phase 10** scope. I am not calling this a defect — errors and cancelled
notices need somewhere to go once the grid owns the Results tab, and the alternative would have
been to drop error display entirely, which is worse.

Record the decision in the session log: state that the `QTextEdit` was retained as a
transitional message surface, that the real messages panel remains Phase 10, and that this was
a deliberate choice rather than an oversight. If you think it should instead be removed and
errors shown some other way, say so and I will take it to the maintainer.

### C4. Two small things

- The new autouse fixture guards with `hasattr(widget, "_schema_workers")`. Every `MainWindow`
  has that attribute — this is the same speculative-guard pattern the plan asked you to remove
  from `closeEvent`, reintroduced in the tests. Drop it, or narrow the `isinstance` check.
- **V6 has no explicit test.** No worker touches the model — I checked, there is no `QThread`
  or `moveToThread` anywhere in the new model or view — so the behaviour is correct. But the
  plan asked for it to be *asserted*. Note that `catalog_model.py:119` already carries a
  `QThread.currentThread() is not self.thread()` guard as precedent. Either add the assertion
  or record explicitly that V6 was verified by inspection rather than by test, and say which.

## Verification before marking complete

- The four V7 mutations, each with its failing node id, `--color=no`, mutation-applied check.
- Corrected session log: 3.14 tally, 3.12 tally, the V8 result (0/50, measured by review), and
  the C3 decision.
- `./run.sh uv run pytest -q` on 3.14 and `--python 3.12` — record both.
  **Remember:** `uv run --python 3.12` re-syncs the shared venv; run
  `./run.sh uv sync --all-extras --dev --python 3.14` afterwards or your next measurement is on
  the wrong interpreter.
- `scripts/orchestration/run-quality-gates` → exit 0.
- `git status --short` → prints nothing.

Only re-run V8 if you modify source code in this round.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests. Do
not modify the Streamlit path. Do not touch `main`. Do not bump the package version. Do not
change the implementation in this round beyond C4's two small items.

## Deferred — unchanged, and correctly out of scope

No human has seen the grid; all Qt tests are offscreen. No performance measurement — do not
imply the migration document's responsiveness targets were met. Export is Phase 12, history v2
is Phase 11, Spark is Phase 13, the messages panel is Phase 10. macOS and Windows unverified.

STATUS: CHANGES_REQUESTED
