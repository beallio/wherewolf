# Review — ui-polish (round 02)

Branch: `feat/ui-polish` @ `f71b135`
Reviewed against: `docs/plans/2026-08-02_ui-polish.md` and review 01

## Verdict

APPROVED.

## Gate status

```text
ruff check   All checks passed
ty check .   All checks passed
pytest       408 passed, 7 deselected   (was 406; +2 tests)
git status   clean
```

## Correction to review 01 — my evidence was wrong

Review 01 stated that Ctrl+C in the Translation tab "still copies the SQL editor" and
showed a clipboard containing `'EDITOR SQL HERE'`. **That measurement was invalid, and the
claim it supported was false.**

The test fixture set the panel text and then called `w.editor.setText(...)`, which fires
`_refresh_translation` and *overwrites the translation panel with a translation of the
editor text*. So the panel really did contain `'EDITOR SQL HERE'` — the clipboard was
correct and my fixture was broken. Ctrl+C was already routing to the focused widget at
`5e30151`, because the `WidgetShortcut` change had done its job.

Re-running the corrected test against `5e30151` separates what was true from what was not:

```text
Ctrl+C (translation focused)  -> 'SELECT\n  id\nFROM t\nLIMIT 3'   PASS  (already worked)
Edit > Copy (translation)     -> ''                                FAIL  (real defect)
Ctrl+C (editor focused)       -> 'SELECT TOP 3 id FROM t'          PASS
```

The change request was therefore **justified in substance but wrong in its stated
evidence**: the keyboard shortcut was fine; the Edit-menu item was editor-scoped and copied
nothing. `f71b135` fixes that real defect with `_dispatch_focused_edit_action`, and both
paths now work.

The fixture now uses Azure SQL input so the editor holds `SELECT TOP 3 id FROM t` while the
panel holds `SELECT id FROM t LIMIT 3` — two texts that cannot be confused — and it asserts
they differ before measuring anything.

## P4 — verified in both directions

```text
editor      : 'SELECT TOP 3 id FROM t'
translation : 'SELECT\n  id\nFROM t\nLIMIT 3'

Ctrl+C    (translation focused) -> the translation    PASS
Edit>Copy (translation focused) -> the translation    PASS
Ctrl+C    (editor focused)      -> the editor text    PASS
```

Focus was asserted (`focusWidget() is te`) before each key press; under the offscreen
platform `setFocus()` is a silent no-op when the widget sits on a non-current tab.

`_dispatch_focused_edit_action` (`main_window.py:767`) walks from `QApplication.focusWidget()`
up the parent chain, with a `ResultTableView` special case so the grid copies its selection.

## Negative controls — run against the full suite

| mutation | result |
|---|---|
| P1: friendly labels → raw sqlglot identifiers | 1 failed, 407 passed |
| P4: `focusWidget()` → `self.editor` | 1 failed, 407 passed |
| P8: About drops `build_identifier()` | 2 failed, 406 passed |
| P9: `Yes`/`No`/`Unknown` → `?` | 1 failed, 407 passed |

Baseline 408 passed, so each costs one or two tests.

**Two mutations initially misled me, recorded so the pattern is not repeated.** A first P1
attempt matched no line — an inapplicable mutation looks exactly like a guard that does not
bite. A first P9 attempt renamed the *column header* rather than the cell values and nothing
failed; that was correct behaviour, because the test asserts on rendered cell content, which
is the more meaningful target. P6 is guarded directly at `tests/test_main_window.py:81`
(`assert not window.main_toolbar.findChildren(QScrollArea)`); my attempted mutation broke
widget construction outright, so that targeted control was inconclusive and the direct
assertion stands in its place.

## Carried forward from review 01 — still verified

P1 friendly names incl. `Azure SQL`; P2 schema dataset selector switching columns; P3
history timestamp/query columns; P5 toolbar tooltips; P6 single toolbar, zero
`QScrollArea`; P7 `Ctrl+F` / `Ctrl+A` / `Ctrl+/`; P8 About with build identifier and
GPL-3.0-only, no MIT; P9 `Name`/`Type`/`Nullable`/`Position` with Yes/No/Unknown.

## The boundary held

Version `0.5.2`, no tag, `main` untouched. `timid = true`, the `pyarrow` import, the
overwrite confirmation, `EngineKind` and the `DIALECT_MAPPING` identifiers all unchanged.

## Deferred

Visual quality — history row colours, toolbar composition at narrow widths, About layout —
remains a manual maintainer check. The update check ships **off by default**; its enabled
path has not been exercised against a live network.

STATUS: APPROVED
