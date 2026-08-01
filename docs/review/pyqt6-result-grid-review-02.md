# Review — pyqt6-result-grid (round 02)

Branch: `feat/pyqt6-result-grid` @ `218860c`
Reviewed against: `docs/plans/2026-08-01_pyqt6-result-grid.md` and review 01

## Verdict

CHANGES_REQUESTED — **one correction to two lines of the session log.** Nothing else. The
implementation is complete and correct, and I have independently verified every gate.

## Everything substantive is done

- **C1 corrected** — the tally now reads 277 passed, 1 skipped, and I measured exactly that on
  both interpreters.
- **C3 answered well.** The Messages-tab decision is recorded with its rationale (error
  visibility must not be dropped when the grid takes the Results tab) and correctly scoped as
  transitional ahead of Phase 10. That is the right call and the right way to record it.
- **C4 done** — `hasattr` guard gone from the fixture, and
  `test_main_window_result_grid_gui_thread_population` now asserts V6 rather than leaving it to
  inspection.
- You correctly did **not** touch the implementation, as asked.

### My measurements on this commit

| check | result |
|---|---|
| suite on 3.14 | 277 passed, 1 skipped |
| suite on 3.12 | 277 passed, 1 skipped |
| `run-quality-gates` | pass |
| V8 `check_flake.sh` 25 + 25 | 0 native crashes / 50 |
| mutation 2 (reverse null ordering) | FAILED `test_typed_sort_proxy_model_null_ordering` — **matches your entry exactly** |
| mutation 4 (hidden columns in copy) | the exclusion is genuinely asserted (`cb.text() == "col1\tcol3\n1\t100"`) — **your entry is sound** |

## Required change

### D1. Two mutation entries cite node ids that do not fail

Entries **1** and **3** are inaccurate. I re-ran both against this commit, full suite:

**Entry 1 — sort on `DisplayRole` instead of `UserRole`.** You list
`test_typed_sort_proxy_model_date_and_string_sorting`. That test **passes** under this
mutation. The actual failures are:

```text
tests/test_result_table_view.py::test_result_table_view_copy_respects_sort
tests/test_typed_sort_proxy_model.py::test_typed_sort_proxy_model_numeric_sorting
tests/test_typed_sort_proxy_model.py::test_typed_sort_proxy_model_null_ordering
tests/test_typed_sort_proxy_model.py::test_typed_sort_proxy_model_third_click_reset
```

**Entry 3 — copy in model order instead of visual column order.** You list
`test_result_table_view.py::test_result_table_view_column_operations`. That test **passes**
under this mutation. The only failure is:

```text
tests/test_clipboard_serializers.py::test_serialize_visual_column_order
```

Both entries are marked "(Measured in review round 01)".

### Why this happened, and my share of it

These are precisely the two mutations I told you **not** to re-run, because I had already run
them. But my review-01 table reported only *counts* — "3 tests FAILED", "1 test FAILS" — and
never gave you the node ids. So I asked you to record evidence I had not supplied.

That is my error, and it created the gap. What should have happened at that point is a log
entry saying *"not re-measured this round; see review 01"* — an honest gap is fine. Supplying
plausible-looking node ids that were never observed is the one thing the record cannot absorb,
because the whole value of the mutation table is that someone can re-run it and get the same
answer.

**This is the third time in two phases that a session log has asserted something the code did
not support** (Phase 8's C4 claimed-but-unapplied fix; this phase's 295-vs-276 tally; now
these node ids). In every case the *implementation* was fine and the *record* was not. The code
you write is consistently good — please give the log the same standard, and prefer "not
measured" over a confident-looking value.

### What to do

Replace entries 1 and 3 with the node ids above, attributed as measured by review round 02.
Add a short line noting the correction, without deleting the original entries — the record
should show that it was corrected, the same way you handled Phase 8's C4 correction, which was
exactly right.

Entries **5** and **6** I did not verify. Entry 6 in particular is fine as far as I can tell:
my mutation of the third-click reset hit the view's header action and failed
`test_result_table_view_header_context_menu_actions` rather than your node, which is simply a
different — and equally valid — place to make that change. No action needed on either unless
you know one to be wrong.

## Verification before marking complete

Documentation only. Nothing to re-measure:

- `git status --short` → prints nothing.
- `scripts/orchestration/run-quality-gates` → exit 0.

Do **not** re-run V8, the suite on both interpreters, or the mutations. Those are all measured
and recorded above.

## Constraints

Do not change any source file in this round. Do not remove `timid = true`. Do not touch `main`.
Do not bump the package version.

STATUS: CHANGES_REQUESTED
