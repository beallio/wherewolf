# Review — pyqt6-result-grid (round 03)

Branch: `feat/pyqt6-result-grid` @ `5cf8663`
Reviewed against: `docs/plans/2026-08-01_pyqt6-result-grid.md` and reviews 01–02

## Verdict

APPROVED.

D1 is resolved exactly as asked, and the way it was resolved is worth naming: the original
entries were **retained** and the corrections added alongside them with attribution, rather
than quietly overwritten. Entry 4 also picked up the confirming evidence. A record that shows
its own correction history is worth more than one that has always looked clean.

Round 03 changed documentation only, as instructed. No source file was touched.

## Final state — all measured by review, not reported

| check | result |
|---|---|
| suite on **3.14** | 277 passed, 1 skipped |
| suite on **3.12** | 277 passed, 1 skipped — identical |
| `run-quality-gates` | pass (ruff check, ruff format, ty, pytest) |
| **V8** `check_flake.sh` 25 + 25 | **0 native crashes / 50** |
| **V2** Streamlit path diff vs `dev` | **literally empty** |
| V7 mutations 1, 2, 3, 4, 6 | all bite; node ids verified |
| `git status --short` | clean |

## What this phase delivered

Thirteen atomic tasks: `PolarsTableModel`, typed values and null rendering,
`TypedSortProxyModel`, Qt-free clipboard serializers, `ResultTableView`, header and body
context menus, column operations, search/filter, `MainWindow` wiring, the Phase 8 follow-ups,
and documentation.

The two pieces of test design most likely to have been done badly were both done well:

- **Sorting is genuinely typed.** `[2, 10, 1] → [1, 2, 10]` is asserted — the lexicographic
  failure mode would give `[1, 10, 2]` — with null ordering stated as a rule and tested in
  both directions.
- **Clipboard output is asserted exactly**, including visual column order, discontiguous
  selection, quoted headers, hidden-column exclusion, and values containing tabs and newlines.
  Not one "clipboard is non-empty" assertion anywhere.

Phase 8's deferred follow-ups are cleared: `QueryController.shutdown()` encapsulates worker
teardown, the private `_workers` reach-through and dead `hasattr` guards are gone, and the
repeated `waitUntil` calls are one autouse fixture that locates windows via
`QApplication.topLevelWidgets()`.

**The 3.12 leg matching 3.14 exactly is the quiet success here.** The floor was restored one
commit before this phase began, and ~1,100 lines of new Qt code landed without a single
3.14-only construct.

## Carried forward to Phase 10

- The `QTextEdit` remains as a transitional **"Messages" tab**. The decision and its rationale
  are recorded in the session log. Phase 10 owns the real messages panel and should absorb or
  replace it.
- V6 is now asserted by `test_main_window_result_grid_gui_thread_population` rather than by
  inspection.

## A process note for future phases

Three times across Phases 8 and 9 a session log asserted something the code did not support:
a claimed-but-unapplied fix, a wrong test tally, and two mutation entries citing tests that do
not fail. Each time the implementation itself was correct.

Part of the last one was my fault — I told the implementer not to re-run two mutations and then
asked them to record node ids I had never supplied. The lesson generalises: **when evidence is
not available, "not measured" is a complete and acceptable answer.** A plausible-looking value
is the only outcome the record cannot absorb, because it defeats the one thing the log exists
for. Worth stating in the plan template rather than catching per-phase.

## Deferred and explicitly NOT verified

No human has seen the grid — all Qt tests are offscreen, and no one has run
`wherewolf-desktop` on a display. **No performance measurement was taken**; the migration
document's responsiveness targets remain unmeasured, and no large frame was benchmarked.
Export is Phase 12, history v2 is Phase 11, Spark is Phase 13, the messages panel is Phase 10.
macOS and Windows are unverified.

STATUS: APPROVED
