# Review — pyqt6-catalog-editor-formatter (round 02)

Branch: `feat/pyqt6-catalog-editor-formatter` @ `ff4624c`
Reviewed against: `docs/plans/2026-07-31_pyqt6-catalog-editor-formatter.md`

## Verdict

CHANGES_REQUESTED — three concrete defects, all small. **All 13 tasks are now present and
round 01's three findings are resolved.** The implementation is close.

Round 01 resolutions confirmed:

- **B1** — Tasks 7-13 delivered. `schema_worker.py`, `statement_service.py`,
  `sql_editor.py` and `formatting_service.py` all exist; `format_sql` is enabled with its
  Phase-3 tooltip cleared; the catalog context menu has Rename Alias, Refresh Schema,
  Copy Alias, Copy File Path and Insert Alias at Editor Cursor; README is updated with
  `cacheBuster=13` and states plainly that query execution is not yet implemented.
- **B2** — `tests/test_catalog_dock.py` now builds real `QDropEvent` objects through a
  `_drop_event()` helper. The stand-in class is gone.
- **B3** — the session log now records that the segfault claim "was not reproducible".
  Thank you for correcting it rather than quietly dropping it.

## Gate status

```text
ruff check .          -> All checks passed!
ruff format --check . -> 103 files already formatted
ty check src/         -> All checks passed!
pytest                -> 179 passed, 1 skipped
git status --short    -> clean
```

Baseline `107 passed, 1 skipped`; round 01 reached 139; now 179. +72 tests overall.

## Required changes

### B4. The macOS Format SQL shortcut is wrong, and its test cannot catch that

`src/wherewolf/desktop/actions.py:33-36`:

```python
if sys.platform == "darwin":
    format_sql.setShortcut(QKeySequence("Meta+Shift+F"))
else:
    format_sql.setShortcut(QKeySequence("Ctrl+Shift+F"))
```

In Qt, `Ctrl` in a `QKeySequence` maps to the **Command** key on macOS, and `Meta` maps to
the **Control** key. So this binds Format SQL to **Control+Shift+F** on macOS, not
`Cmd+Shift+F` as the plan (Task 12) and migration-document Section 12.4 require.

The platform branch is not merely wrong, it is unnecessary: a plain
`QKeySequence("Ctrl+Shift+F")` already yields `Cmd+Shift+F` on macOS and
`Ctrl+Shift+F` elsewhere, because Qt performs that mapping itself.

The accompanying test cannot detect this. `tests/test_actions.py:12-17`:

```python
def _expected_format_shortcut() -> str:
    return (
        QKeySequence("Meta+Shift+F").toString()
        if sys.platform == "darwin"
        else QKeySequence("Ctrl+Shift+F").toString()
    )
```

It recomputes the expectation with the **same branch and the same literals** as the
implementation, so it is a tautology — it would pass for any value. And because CI is
Linux-only, the `darwin` branch never executes at all. I confirmed that by replacing the
darwin literal with `"Meta+Shift+ZZZ_ABSURD"`: `5 passed`, nothing failed.

Fix: delete the platform branch and set `QKeySequence("Ctrl+Shift+F")` unconditionally.
Then assert the concrete expected sequence directly rather than recomputing it — for
example that `actions.format_sql.shortcut() == QKeySequence("Ctrl+Shift+F")` — so the
assertion is independent of the implementation's expression.

### B5. Case-insensitive alias uniqueness is not actually tested

Deleting **every** `.casefold()` call from `src/wherewolf/services/catalog_service.py`
breaks no test: `11 passed`. Two tests are named for this behavior but neither exercises a
case difference.

`tests/test_catalog_service.py:100` — `test_rename_rejects_casefold_collision` renames to
`service.snapshot()[1].alias`, i.e. the **exact** existing alias. A plain `==` comparison
satisfies it.

`tests/test_catalog_service.py:64` — `test_add_paths_alias_uniqueness_is_casefold` adds
`Orders.csv` then `orders.csv` and expects `orders_2`. But alias generation lowercases the
stem, so both become `orders` before any comparison; exact equality again suffices.

The behavior itself **is** correct — I verified directly that renaming to `'ORDERS'`,
`'Orders'` and `'orders'` are all rejected when `orders` exists. The problem is that
nothing protects it. Strengthen both tests so they fail when `.casefold()` is removed:
rename to a case **variant** of an existing alias, and construct the add-path case so the
two aliases differ only by case at comparison time.

That same file has a smaller problem worth fixing while you are in it: lines 66-69 call
`add_paths` on `Orders.csv`/`orders.csv` **before** writing those files, then create them
afterwards. Write the fixtures first so the test does not depend on `add_paths` accepting
non-existent paths.

### B6. The primary toolbar has no `objectName`, so its layout is not persisted

`QMainWindow.saveState()` emits:

```text
QMainWindow::saveState(): 'objectName' not set for QToolBar 0x... 'Primary'
```

Confirmed: `toolbar.objectName()` is `''` while `dock.objectName()` is
`'dataset_catalog_dock'`. Qt identifies toolbars and docks by `objectName` when saving and
restoring state, so the toolbar's position and visibility are silently dropped from the
persisted layout that Phase 3 added and `SettingsService` stores.

Set a stable `objectName` on the toolbar (e.g. `"primary_toolbar"`), matching the dock's
existing convention. Add an assertion that `saveState()` produces no Qt warning, or at
minimum that every `QToolBar` and `QDockWidget` under the main window has a non-empty
`objectName` — the current layout-persistence tests pass despite this, so they need the
extra assertion to close the gap.

## Process note

Tasks 7-13 landed as a **single** commit, `ff4624c` ("feat(editor): add desktop catalog
schema, editor, and formatting foundation"), covering seven plan tasks across two phases.
The plan specifies a commit per task with the message given in each. Round 01's commits
were correctly task-sized, so this is a regression in granularity, not a misunderstanding.

Do not rewrite the existing history for this. Land the B4-B6 fixes as separate, properly
scoped commits.

## Mutation results — I ran all six

Four bite. One found a real gap (B5). One was **my** faulty mutation, not a test gap:

| # | Mutation | Result |
|---|---|---|
| 1 | statement locator splits naively on every `;` | **bites** — 10 tests, incl. all four quote/comment cases |
| 2 | formatter keeps only the first statement | **bites** — `test_multiple_statements_are_all_retained`, `test_comments_survive_formatting` |
| 3 | parse error returns `""` instead of the original | **bites** — `test_parse_error_returns_original_and_diagnostic` |
| 4 | remove every `.casefold()` | **NO BITE** — see B5 |
| 5 | remove `beginUndoAction`/`endUndoAction` | no bite, but **not** a test gap — see below |
| 6 | editor builds its own Format `QAction` | **bites** — `test_format_action_is_shared_with_editor_context_action` |

On #5: removing the undo-transaction pair alone changes nothing observable, because
`replaceSelectedText` is already a single atomic edit — my mutation was ineffective rather
than the test being hollow. I re-ran it as a genuinely split edit (`replaceSelectedText("")`
followed by `insert(...)`, no wrapper) and
`test_format_sql_one_undo_restores_entire_text` **failed** as it should. The single-undo
guarantee is properly protected. Keep the `beginUndoAction`/`endUndoAction` pair — it is
correct defensive practice even though today's implementation does not depend on it.

The tree was clean after every mutation was reverted.

## Also verified

- Format SQL is the **same `QAction` object** across toolbar, Query menu and the editor
  context menu — measured on a live offscreen window, not read from source.
- `format_selection_or_statement` restores cursor position, first visible line and
  horizontal scroll, and returns early without touching the document when the formatter
  reports diagnostics.
- The Streamlit path is untouched: `git diff --name-only dev..HEAD` over `app.py`,
  `engines.py`, `ui/`, `export/`, `storage/`, `constants.py` and `.streamlit/` is empty.
- Round 01's accepted deviations (`entries` as a property, `add_paths` returning
  `CatalogServiceReport`) are unchanged, as agreed.

## Not verified

- No native dialog, no real drag from a file manager, no real window — all offscreen, as
  the plan's deferred list states.
- macOS behavior generally, and B4 specifically: the corrected shortcut still cannot be
  proven on Linux CI. Assert the key sequence, and note in the session log that the actual
  macOS binding remains unverified until the Phase 15 cross-platform matrix.

STATUS: CHANGES_REQUESTED
