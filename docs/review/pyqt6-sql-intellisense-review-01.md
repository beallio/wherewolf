# Review — pyqt6-sql-intellisense (round 01)

Branch: `feat/pyqt6-sql-intellisense` @ `b30a34a`
Reviewed against: `docs/plans/2026-07-31_pyqt6-sql-intellisense.md`

## Verdict

CHANGES_REQUESTED — **one finding, and it is a test gap rather than a bug.** The feature
itself works; I verified the three headline cases by driving the service directly.

All 12 tasks were delivered in a single round, in order, each as its own commit with its own
test file. That is the cleanest round this project has had.

## Gate status

```text
ruff check .          -> All checks passed!
ruff format --check . -> 112 files already formatted
ty check src/         -> All checks passed!
pytest                -> 222 passed, 1 skipped (baseline 179; +43)
coverage TOTAL        -> 85%
check_flake.sh 25     -> PASSED: 0 native crashes in 25 runs
git status --short    -> clean
```

The `check_flake.sh` result matters: this slice adds Qt widget and event-driven code, which
is the exact area that produced the coverage crash fixed in `a913e04`. It has not returned.

## Verified working — I drove these myself, not via the tests

The three minimum cases from migration-document Section 12.3, exercised through
`SqlCompletionService.complete()` with a real two-table catalog:

```text
CASE 1  SELECT * FROM <cursor>
        -> [('customers','table'), ('orders','table')]                        PASS

CASE 2  SELECT o.<cursor> \n FROM orders AS o
        -> ['customer_id', 'order_id', 'total']                               PASS
           (only orders columns; nothing from customers leaked)

CASE 3  SELECT * FROM orders o JOIN customers c ON o.customer_id = c.<cursor>
        -> ['city', 'customer_id', 'name']                                    PASS
           (only customers columns)
```

Case 2 is the one that matters most and it returns *only* the target table's columns, not
merely "something".

Also confirmed:

- **The completion modules are genuinely Qt-free.** `completion_service.py`,
  `completion_context.py`, `sql_metadata.py` and `domain/models.py` contain no PyQt6
  imports, so the logic is testable without a widget.
- **Streamlit path untouched:** `git diff --name-only dev..HEAD` over `app.py`,
  `engines.py`, `ui/`, `export/`, `storage/`, `constants.py`, `.streamlit/` is empty.
- **Every implementation commit pairs one `src/` file with one `tests/` file** — 12 commits,
  no implementation landed without a test.

## Required change

### B1. The completion threshold is configured but its effect is untested

Making the editor ignore the threshold entirely — replacing the guard at
`src/wherewolf/desktop/widgets/sql_editor.py:94`

```python
if len(cursor_ctx.prefix) < self.completion_threshold:
    return
```

with `if False:` so completion is requested on every keystroke — breaks **no test**:
`14 passed`. The mutation was confirmed to apply before the run.

`tests/test_sql_editor.py:153` `test_sql_editor_completion_threshold_and_ctrl_space` is
named for this behavior but only asserts configuration values:

```python
assert editor.completion_threshold == 2
assert editor.completion_enabled is True
assert editor.show_completion_action.shortcut().toString() == "Ctrl+Space"
```

It never issues a completion request, so it cannot detect whether the threshold does
anything. Nothing in the suite calls `editor.request_completion(forced=False)` — the only
call is `forced=True` at line 218, which deliberately bypasses the very branch that holds
the threshold and enable/disable gates.

This is the same shape as two defects already found in this project: the casefold tests that
passed on exact equality, and the Format SQL shortcut test that recomputed its expectation
from the implementation's own branch. A test that asserts a setting's *value* is not a test
of the setting's *effect*.

Plan Task 11 required these behaviors specifically. Add tests that drive the unforced path
and assert on whether the completion service was called (spy it):

1. a prefix **shorter** than the threshold does **not** request completion;
2. a prefix **at or above** the threshold **does**;
3. with `completion_enabled` set to `False`, typing does **not** request completion, but
   `Ctrl+Space` (`forced=True`) still does;
4. a changed threshold persisted through `SettingsService` actually changes the trigger
   point — set it to 3, confirm a 2-character prefix no longer triggers.

Each must fail if the corresponding guard is removed. Verify that yourself before marking
the round complete: re-run with `if False:` substituted at line 94 and confirm your new
tests go red.

Do not change any production code for this. `sql_editor.py:90-95` is correct as written —
this is purely missing test coverage.

## Non-blocking observations

### N1. `services/__init__.py` makes the Qt-free modules transitively import Qt

The completion modules themselves are clean, but
`from wherewolf.services.completion_service import SqlCompletionService` loads
`PyQt6.QtCore`, because `src/wherewolf/services/__init__.py` eagerly imports
`settings_service`, which wraps `QSettings`.

This is the same pattern that `src/wherewolf/execution/__init__.py` solved with a lazy
`__getattr__` in the first slice. It is **not** blocking here: unlike pyspark, PyQt6 is a
mandatory dependency, so nothing breaks. But if a future phase wants the service layer
usable headlessly (a CLI, a faster unit-test process), this is the thing to fix, and doing
it consistently with `execution/__init__.py` would be tidy. Note it in the session log; do
not change it in this round.

### N2. `test_completion_service.py` now holds 22 tests

Tasks 5-9 all append to one file, which the plan directed so `check_tdd.sh` stays satisfied.
It is getting long. Splitting it is not worth churn now, but worth considering when Phase 8
adds more.

## Mutation results

Six checks. Five bite; one found B1. Tree was clean after every revert.

| # | Mutation | Result |
|---|---|---|
| 1 | string/comment suppression removed from `detect_context` | **bites** — `test_detect_context_suppressed_strings_and_comments` |
| 2 | `alias.` ignores the qualifier, returns all catalog columns | **bites** — `test_qualified_alias_returns_only_target_table_columns`, `test_join_qualified_alias_prioritises_joined_table_columns`, `test_qualified_unknown_alias_returns_no_columns` |
| 3 | `sort_key` collapsed to a constant | **bites** — `test_completion_ranking_order` |
| 4 | identifier quoting dropped | **bites** — `test_identifier_quoting_and_function_parens` |
| 5 | completion threshold ignored | **NO BITE** — see B1 |
| 6 | typed prefix not replaced on insertion | **bites** — `test_completion_adapter_replaces_only_typed_prefix` |

A methodological note, because it nearly produced two false findings against you: my first
attempts at mutations 1, 2 and 3 were faulty — one inserted `pass` after a function
signature (leaving the real body intact), one used replacement strings that matched nothing,
and my result parser missed pytest's ANSI-coloured `FAILED` lines. All three initially
reported "NO BITE". Only mutation 5 survives once the harness verifies the mutation actually
applied and the output is parsed with `--color=no`. **B1 is the only real gap.**

## Not verified

- **No completion popup was ever seen.** All Qt tests run offscreen; the adapter is asserted
  through QScintilla's API. That the popup renders, positions correctly and is readable is
  manual and deferred.
- **No real typing.** Debounce and threshold behavior is exercised through direct calls, not
  keyboard timing.
- **macOS and Windows unverified**, including whether `Ctrl+Space` collides with the macOS
  input-source switcher — worth recording as a known risk.
- **The 100 ms latency target in Section 12.3 was not measured.**
- **Completion quality is bounded by cached schema**: entries with `schema is None`
  contribute no columns, by design, to avoid blocking the GUI thread.
- **No query executes.** Phase 8.
- **CI unproven until first push.**

STATUS: CHANGES_REQUESTED
