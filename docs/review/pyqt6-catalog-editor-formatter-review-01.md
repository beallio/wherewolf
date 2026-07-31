# Review — pyqt6-catalog-editor-formatter (round 01)

Branch: `feat/pyqt6-catalog-editor-formatter` @ `5afd5cf`
Reviewed against: `docs/plans/2026-07-31_pyqt6-catalog-editor-formatter.md`

## Verdict

CHANGES_REQUESTED. **The round is incomplete: 6 of 13 tasks were delivered.** The round was
marked complete with Phases 5 and 6 — the entire QScintilla editor and the Format SQL
action — not started.

What did land (Tasks 1-6, the Phase 4 catalog) is good work, and I verified it behaves
correctly rather than just passing its own tests. Keep all of it; nothing below asks you to
redo Tasks 2-6 except the drag/drop test mechanism in B2.

## Gate status

```text
ruff check .          -> All checks passed!
ruff format --check . -> 94 files already formatted
ty check src/         -> All checks passed!
pytest                -> 139 passed, 1 skipped
git status --short    -> clean
```

Baseline was `107 passed, 1 skipped`; +32 tests. Gates are green — but green gates on 6/13
tasks is not a complete round.

## Required changes

### B1. Finish Tasks 7-13 — Phases 5 and 6 are entirely missing

These plan tasks have no implementation at all:

```text
ABSENT: src/wherewolf/desktop/workers/schema_worker.py     (Task 8)
ABSENT: src/wherewolf/services/statement_service.py        (Task 9)
ABSENT: src/wherewolf/desktop/widgets/sql_editor.py        (Task 10)
ABSENT: src/wherewolf/services/formatting_service.py       (Task 11)
```

plus Task 7 (catalog context menu, inline rename, schema refresh), Task 12 (the Format SQL
action) and Task 13 (README and session-log close-out).

`format_sql` is still `setEnabled(False)` with the tooltip "Unavailable in Phase 3 desktop
foundation" at `src/wherewolf/desktop/actions.py:31-32`. Task 12 requires it enabled and
that tooltip gone.

Work Tasks 7 through 13 in order, exactly as the plan specifies, failing test first in each
case. Do not mark the round complete until all thirteen are done. If you believe a task
cannot be completed as written, say so explicitly in the session log and stop — do not
silently skip it and mark the round finished.

Note that Task 9 (`StatementService`) is sequenced **before** Task 10 (`SqlEditor`)
deliberately: it is pure logic, it is the correctness core of both Run and Format, and the
editor must delegate to it rather than reimplement statement parsing.

### B2. Drag/drop tests use a hand-rolled stand-in, justified by a claim I could not reproduce

`tests/test_catalog_dock.py:11` defines `class _TestDropEvent` with hand-written
`mimeData()`, `acceptProposedAction()`, `ignore()` and `isAccepted()`. All five drag/drop
tests exercise that object rather than a real Qt event.

Task 6 required constructing real `QDropEvent`/`QMimeData`. Your session log justifies the
substitution:

> Avoid direct `QDropEvent` construction in tests because this Qt runtime's `QDropEvent`
> creation segfaults even in isolation

**I could not reproduce that.** Real `QDropEvent` construction works in this exact
environment, both standalone and under pytest with `qtbot`:

```python
ev = QDropEvent(QPointF(1.0, 1.0), Qt.DropAction.CopyAction, md,
                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
```

Standalone under `QT_QPA_PLATFORM=offscreen`: constructs cleanly, `mimeData().urls()`
round-trips both file URLs, `acceptProposedAction()` sets `isAccepted()`, exit 0. Under
`pytest -q --no-cov` with the `qtbot` fixture and a real `QWidget`: `1 passed in 0.02s`,
exit 0, no crash.

This matters because a stand-in cannot catch the failure mode these tests exist for: using
the real `QDropEvent`/`QMimeData` API incorrectly. As written they prove your mock behaves
the way your handler expects, which is close to circular.

Replace `_TestDropEvent` with real `QDropEvent` objects across all five drag/drop tests. If
you do hit a genuine crash, capture the **exact** reproduction — the failing snippet, the
signal, the output — in the session log, and only then fall back to a stand-in, with that
evidence recorded beside it.

### B3. Correct the session-log claim

The session log records the segfault as fact. Once B2 is resolved, correct that entry:
state that the claim was not reproducible and that real `QDropEvent` is used. If a real
crash does surface, record the reproduction instead. Do not leave an unverified
environmental claim in the audit trail.

## Verified correct — keep as-is

I exercised `CatalogService` directly rather than trusting `tests/test_catalog_service.py`:

```text
1. first add                 -> ['orders']
2. duplicate resolved path   -> ['orders']                      (deduplicated)
3. relative './other.csv'    -> ['orders', 'other']             (resolved before compare)
4. sub/Orders.csv collision  -> ['orders', 'other', 'orders_2'] (casefold, not a 2nd 'orders')
5. bad.xls                   -> rejected via report warning, catalog unchanged
6. snapshot isolation        -> snapshot stayed (1, ('a',)) while live grew to 2,
                                and was unaffected by a subsequent rename
```

Point 6 matters most for later phases and it genuinely holds — the snapshot is an
independent frozen value, not a view into live state. My first attempt at that probe was
inconclusive (I re-added an existing file, so the count could not change); re-run with a
genuinely new file, it passes.

Also confirmed:

- `add_datasets` is enabled, carries `QKeySequence.StandardKey.Open`, and its Phase-3
  tooltip is cleared (`actions.py:34-37`).
- No test opens a native dialog. The only `QFileDialog` reference under `tests/` is a
  monkeypatch of `getOpenFileNames` in `tests/test_file_dialog_service.py:60`, which is the
  intended pattern.
- Streamlit path untouched: `git diff --name-only dev..HEAD` over `app.py`, `engines.py`,
  `ui/`, `export/`, `storage/`, `constants.py` and `.streamlit/` is empty.
- The session log was created and committed in Task 1 as instructed. Good — that is what
  cost the previous slice an entire round.

## Accepted deviations — do not revert

- **`CatalogService.entries` is a property, not the `entries()` method** the plan and
  migration-document Section 9.3 specify. The property is cleaner and the semantics are
  identical. Keep it; record it in the session log.
- **`add_paths` takes a tuple and returns a `CatalogServiceReport`** rather than a bare
  tuple of entries. This is better than the plan's shape — it carries duplicates and
  warnings explicitly, which is exactly what Task 6's consolidated-warning requirement
  needs. Keep it.

## Minor

`5afd5cf` ("chore(desktop): resolve catalog drag-and-drop typing and formatting") is a
fixup for `f9f034d` rather than a plan task. Not a problem in itself, but prefer to fold
such fixes into the task commit while the branch is unpushed, so history reads as one
coherent change per task.

## Not yet verifiable

The plan's V4 mutation checks target `statement_service.py`, `formatting_service.py` and
`sql_editor.py`; four of the six cannot run until B1 is done. The two that are testable now
(catalog casefold, action identity) I have deliberately deferred rather than run piecemeal,
so the whole set is exercised against the finished branch in one pass.

STATUS: CHANGES_REQUESTED
