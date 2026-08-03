# Review — pyqt6-schema-translation-messages (round 02)

Branch: `feat/pyqt6-schema-translation-messages` @ `832a953`
Reviewed against: `docs/plans/2026-08-01_pyqt6-schema-translation-messages.md` and review 01

## Verdict

APPROVED.

All three review items are resolved, and E1 — the real defect — is fixed and **verified by
re-applying the mutation that previously slipped through**.

## E1 — fixed, and confirmed by counterfactual

The guard now drives the **view** rather than the proxy, and populates the editor so the
execution path is genuinely reachable:

```python
window.editor.setText("SELECT * FROM preview")
...
window.result_table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
window.result_table_view.sortByColumn(0, Qt.SortOrder.DescendingOrder)
window.result_table_view.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
```

Both changes were needed; either alone would have left the hole open.

I re-applied mutation 6 in the same form that previously passed — wiring
`horizontalHeader().sortIndicatorChanged` to `_on_run_triggered` — and the guard now **fails**:

```text
FAILED tests/test_result_table_view.py::test_local_sort_does_not_rerun_query
1 failed, 6 passed
```

Your own log records `executed_count == 3, expected 0`, which matches. The phase's central
safeguard now works.

## E2 — the session log is now a real record

This is a substantial improvement over round 01, and over the last several phases:

- every task recorded with its commit sha, Tasks 10 and 11 included;
- V1 tallies for **both** interpreters, with the venv-restore step noted;
- **V10 correctly attributed** — "not re-run in this repair because source lifetime behavior
  did not change", citing review 01's independent 0/50. That is exactly right: it neither
  claims a measurement it did not take nor leaves a gap unexplained. That reasoning is sound —
  E3 changes a Python exception boundary, not Qt object lifetime;
- **all six V8 mutations with the node id actually observed**, including the observed value for
  mutation 6.

Mutation 2's node id matches my independent measurement exactly. This is the standard the plan
asked for.

## E3 — fixed

```python
except Exception as exc:  # noqa: BLE001 - display translation failures instead of raising.
```

The redundant tuple is gone and the comment states why the boundary is broad. The now-unused
`TranslationError` import was removed with it.

## Final state — measured by review

| check | result |
|---|---|
| suite on **3.14** | 307 passed, 1 skipped |
| suite on **3.12** | 307 passed, 1 skipped — identical |
| `run-quality-gates` | pass |
| **V10** crash gate (round 01) | 0 native crashes / 50 |
| **V9** 3.14-only syntax | none |
| V8 mutation 2 | bites, node id confirmed |
| **V8 mutation 6** | **now bites** — was the defect |
| `git status --short` | clean |

## What this phase delivered

Schema panel with error states, identifier quoting, schema-column insertion, translation view
model and panel, a real messages panel replacing the Phase 9 placeholder, full-query `ORDER BY`
generation, the apply-order action, request details and metrics, and the local-sort guard.

Two pieces of design deserve specific credit:

- **`ORDER BY` around a `LIMIT` query wraps it in a subquery**
  (`SELECT * FROM (SELECT * FROM users LIMIT 10) AS _subquery ORDER BY id DESC`). A naive
  append would have silently changed *which* rows came back. That is the kind of thing that
  produces wrong answers rather than errors.
- **The local-sort/full-query-ordering distinction is now enforced by a test that can actually
  fail.** Sorting a preview stays free; ordering the full result set stays explicit.

`registry.py` was extended to populate `ColumnSchema.nullable`, which the schema panel needs;
`_frame_to_columns` remains in use by the Spark path, so nothing went dead.

## Note on this round

Round 02 ran on **codex `gpt-5.6-terra`** after agy hit its individual quota
(`Resets in 1h42m`). The supervisor burned five launch attempts in about twenty seconds
because a quota failure is indistinguishable from a mid-turn exit, and the implementer's stderr
never reaches the supervisor log. Worth hardening in the orchestration adapter: a launch that
fails before producing any output should surface the implementer's error rather than silently
retrying.

## Deferred — unchanged and correctly recorded

No human has seen these panels; all Qt tests are offscreen. No performance measurement — the
migration document's responsiveness targets remain unmeasured. History v2 is Phase 11, export
Phase 12, Spark Phase 13, Streamlit removal Phase 14. macOS and Windows unverified. Spark
schema and translation paths unverified — DuckDB only.

STATUS: APPROVED
