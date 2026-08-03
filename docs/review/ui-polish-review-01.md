# Review — ui-polish (round 01)

Branch: `feat/ui-polish` @ `5e30151`
Reviewed against: `docs/plans/2026-08-02_ui-polish.md`

## Verdict

CHANGES_REQUESTED — **one defect: P4 is not fixed.** The other eight items are correct and
verified; do not redo them.

## Gate status

```text
ruff check   All checks passed
ty check .   All checks passed
pytest       406 passed, 7 deselected
git status   clean
```

Gates are green. The defect below is a behaviour the suite does not currently cover.

## Required changes

### K1 — Ctrl+C in the Translation tab still copies the SQL editor

This is the exact defect the maintainer reported, and it still reproduces. Measured with
focus **confirmed** on the translation panel's `QPlainTextEdit`:

```text
focus widget: QPlainTextEdit   is translation edit: True
Ctrl+C in translation panel -> 'EDITOR SQL HERE'      <- wrong, that is the editor's text
Ctrl+C in editor            -> 'EDITOR SQL HERE'      <- correct
```

The translation panel contained `'TRANSLATED SQL HERE'` and it was fully selected.

**Why the current approach is insufficient.** `sql_editor.py:173-198` sets
`Qt.ShortcutContext.WidgetShortcut` on the editor's actions, which is the right instinct.
But `main_window.py:775` still does:

```python
undo, redo, cut, copy, paste, toggle_comment = self.editor.edit_actions
```

and adds those same action objects to the Edit menu. A QAction placed in the window's
menubar is registered at window scope, which defeats the `WidgetShortcut` setting — so the
editor's copy still wins regardless of where focus is.

**Required change.** The Edit menu's clipboard and select-all entries must dispatch to the
**focused widget**, not to the editor. The usual shape is a `MainWindow`-owned action that
resolves `QApplication.focusWidget()` and invokes `copy()`/`cut()`/`paste()`/`selectAll()`
on it when that widget supports the operation, falling back sensibly otherwise. The
editor's own `WidgetShortcut` actions can stay for its context menu.

The results grid must copy its own selection too — it is the third widget a user will try
this in.

**How to verify it — this is the part that failed this round.** A test that triggers the
menu `QAction` proves nothing here, because that action is editor-scoped by construction;
it passes both before and after the fix. Drive a real key event at a genuinely focused
widget:

```python
tabs.setCurrentIndex(<Translation tab>)      # the widget must be visible to take focus
te.setFocus(Qt.FocusReason.MouseFocusReason)
assert QApplication.focusWidget() is te      # assert focus actually moved
QTest.keyClick(te, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
```

Under the offscreen platform `setFocus()` silently does nothing if the widget sits on a
non-current tab — my first attempt hit exactly that and produced a meaningless empty
clipboard. **Assert `focusWidget() is` the target before pressing the key**, or the test is
not measuring what it claims.

Required assertions: with the translation panel focused the clipboard gets the
*translation* text and **not** the editor text; with the editor focused it gets the editor
text. Both directions, in one test.

### K2 — negative controls still owed

The plan required them for tasks 1, 4, 6, 8 and 9, run against the **full** suite. Provide
them next round, including the new P4 test. Confirm each mutation actually modified the
file before trusting its result — a mutation that fails to apply looks identical to a guard
that does not bite.

## Verified and correct — do not revisit

| item | evidence |
|---|---|
| P1 friendly dialect names | `tsql` renders as `Azure SQL`; 0 raw-lowercase leftovers; targets read `Athena`, `Bigquery`, `Clickhouse`, … |
| P2 schema dataset selector | `schema_dataset_selector` present; switching shows `customers → [customer_id, age]` vs `loans → [loan_id, amount, term]`; header reads `loans — /tmp/loans.parquet (parquet) — 3 columns` |
| P3 history columns | separate timestamp/query columns with alternating rows |
| P5 toolbar tooltips | every toolbar action has non-empty tooltip |
| P6 single toolbar | `QScrollArea` count is **0**; controls still reachable |
| P7 shortcuts | Find/Replace `Ctrl+F`, Select All `Ctrl+A`, Toggle Comment `Ctrl+/` |
| P8 About | shows `build_identifier()` and GPL-3.0-only, no MIT mention |
| P9 schema detail | headers `['Name','Type','Nullable','Position']`; rows render `Yes` / `No` / `Unknown` distinctly |

## Constraints

Do not bump the version, tag, or touch `main`. Do not remove `timid = true`, the `pyarrow`
import, or the overwrite confirmation. Do not change `EngineKind` or the sqlglot
identifiers in `DIALECT_MAPPING`. Do not reintroduce a `QScrollArea` in the toolbar.

STATUS: CHANGES_REQUESTED
