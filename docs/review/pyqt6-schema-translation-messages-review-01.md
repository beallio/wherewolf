# Review — pyqt6-schema-translation-messages (round 01)

Branch: `feat/pyqt6-schema-translation-messages` @ `789d850`
Reviewed against: `docs/plans/2026-08-01_pyqt6-schema-translation-messages.md`

## Verdict

CHANGES_REQUESTED — **one real defect, and it is in the one guard this phase exists to
provide.** Everything else is good, and some of it is very good.

## What you did well

- **Twelve atomic commits in plan order**, with the Qt-free logic (quoting, translation view
  model, ORDER BY builder) landing before the widgets built on it.
- **V5 is exemplary.** Exact SQL assertions, and the hard cases are all covered:

  ```text
  SELECT * FROM users ORDER BY id ASC
  SELECT * FROM users ORDER BY "first name" DESC          <- quoted
  SELECT * FROM items ORDER BY "select" ASC               <- reserved word
  SELECT * FROM (SELECT * FROM users LIMIT 10) AS _subquery ORDER BY id DESC
  ```

  That last one is the subtle one and you got it right: wrapping a `LIMIT` query in a subquery
  means ordering cannot silently change *which* rows come back. A naive append would have
  produced a different result set.
- **Identifier quoting is asserted exactly**, including bare identifiers, mixed case, spaces
  and reserved words.
- **Task 8 is clean.** `_results_text` is fully removed (zero references), the messages panel
  replaces it, and the FAILED and CANCELLED paths from Phase 8 both still surface.
- The unplanned `registry.py` change is **justified** — `inspect_schema` now builds
  `ColumnSchema` directly and populates `nullable`, which the schema panel needs.
  `_frame_to_columns` is still used by the Spark path, so nothing went dead. Note it in the log
  as a deliberate enabling change rather than leaving it unexplained.

### Measurements I ran myself

| check | result |
|---|---|
| suite on **3.14** | 307 passed, 1 skipped |
| suite on **3.12** | 307 passed, 1 skipped — identical |
| `run-quality-gates` | pass |
| **V10** `check_flake.sh` 25 + 25 | **0 native crashes / 50** |
| **V9** 3.14-only syntax | none |
| V8 mutation 2 (legacy `translate()`) | FAILED `test_translation_view_model_multi_statement_no_statement_loss` |
| **V8 mutation 6 (local sort re-executes)** | **DID NOT BITE — see E1** |

V10 is satisfied. You do not need to re-run it unless you change source in this round.

## Required changes

### E1. The no-rerun guard does not detect the regression it exists to prevent

`tests/test_result_table_view.py::test_local_sort_does_not_rerun_query` counts executions
correctly — that part is right. But it drives the **proxy model directly**:

```python
window.result_table_view.proxy_model().sort(0, Qt.SortOrder.AscendingOrder)
```

A real user sorts by clicking a header, which goes through the **view**. I applied V8's
mutation 6 in the most realistic form — wiring the header's sort signal in `MainWindow` to a
re-execution:

```python
_hdr.sortIndicatorChanged.connect(lambda *_a: self._on_run_triggered())
```

**All 7 tests in the file still passed.** The guard does not catch it.

I verified the mutation was genuinely live rather than inert, because an inert mutation proves
nothing:

| action | executions |
|---|---|
| populate grid | 0 |
| `sortByColumn(...)` — real header path | **1** ← regression fires |
| `proxy_model().sort(...)` — what the guard tests | 1 (unchanged) |

**Two independent reasons it cannot detect this:**

1. It bypasses the view. `proxy.sort()` does not change the view's sort indicator, so anything
   connected to the header signal never fires.
2. It never sets editor text. `_on_run_triggered` returns early on empty SQL
   (`"No SQL statement to run"`), so even routed through the view it would not reach
   `execute`. My first probe missed this and produced a false negative until I set the text.

**A green test asserting the wrong path is worse than no test**, because it licenses exactly
the change it was written to block. This is the phase's central safeguard — the whole
local-sort-vs-full-query-ordering distinction rests on it.

**Fix:** drive the guard through the view (`sortByColumn`, or a real header click via
`qtbot`), **and** populate the editor so the execution path is genuinely reachable. Then
re-apply mutation 6 at the header-signal level and confirm the test now FAILS. Paste both the
mutation and the failing node id.

### E2. The session log stops at Task 1

The log records the baseline correctly and with the right discipline — "measured via
`./run.sh uv run pytest -q`" is exactly the standard asked for. But it then ends:

```text
## Task Log
- Task 1: Record baseline and session log.
```

Tasks 2–13 are unrecorded, and there is no final tally, no V-by-V evidence, no mutation table
and no crash-gate result — despite all thirteen tasks being implemented and committed.

The plan's recording rule says **"not measured" is a complete and acceptable answer.** That
still requires the entry to exist. An absent record is not the same as an honest one.

Record: the per-task results, the final tally on **both** interpreters, the V8 mutation table
with the node ids **you actually observed**, and V10 (0/50, measured by review — cite it as
such). Where you did not run something, write "not measured" and say so plainly.

### E3. A redundant exception tuple

`src/wherewolf/services/translation_view_model.py`:

```python
except (TranslationError, ValueError, Exception) as exc:  # noqa: BLE001
```

`Exception` subsumes both `TranslationError` and `ValueError`, so the specific types are dead.
It reads as narrow handling when it is in fact catch-all. Either catch the specific types, or
catch `Exception` alone and let the comment say why the boundary is broad.

## Verification before marking complete

- The corrected E1 guard, plus mutation 6 re-applied at the header level and the resulting
  **failing** node id.
- Session log per E2.
- `./run.sh uv run pytest -q` on 3.14 and `--python 3.12` — record both.
  **Remember:** `uv run --python 3.12` re-syncs the shared venv; run
  `./run.sh uv sync --all-extras --dev --python 3.14` afterwards.
- `scripts/orchestration/run-quality-gates` → exit 0.
- `git status --short` → prints nothing.

Re-run V10 only if you change source beyond the guard test and E3.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests. Do
not use the legacy `Translator.translate()` in production code. Do not modify the Streamlit
path. Do not touch `main`. Do not bump the package version.

## Deferred — unchanged

No human has seen these panels; all Qt tests are offscreen. No performance measurement. History
v2 is Phase 11, export Phase 12, Spark Phase 13, Streamlit removal Phase 14. macOS and Windows
unverified. Spark schema and translation paths unverified — DuckDB only.

STATUS: CHANGES_REQUESTED
