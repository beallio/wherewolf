# Review — pyqt6-catalog-editor-formatter (round 03)

Branch: `feat/pyqt6-catalog-editor-formatter` @ `1f29727`
Reviewed against: `docs/plans/2026-07-31_pyqt6-catalog-editor-formatter.md`

## Verdict

CHANGES_REQUESTED — **one item, documentation only. Change no code.**

All three round-02 findings are fixed and I verified each by re-running the mutation that
exposed it. The implementation is done. The only thing outstanding is that the session log
stops at the round-02 B2 correction and does not record round 03 at all.

## Gate status

```text
ruff check .          -> All checks passed!
ty check src/         -> All checks passed!
run-quality-gates     -> quality gates passed
pytest                -> 179 passed, 1 skipped
git status --short    -> clean
```

## Round-02 findings: all verified fixed

Each was re-tested with the same mutation that previously found nothing.

**B4 — macOS shortcut.** `actions.py:32` is now an unconditional
`QKeySequence("Ctrl+Shift+F")`; the `sys.platform == "darwin"` branch is gone, so Qt's own
mapping yields `Cmd+Shift+F` on macOS. The test now asserts the concrete sequence
(`tests/test_actions.py:24`) instead of recomputing it from the implementation's branch.

Re-run: changing the literal to `Ctrl+Shift+G` now **fails**
`test_build_actions_contains_expected_shortcuts_and_states` and
`test_format_action_is_enabled_and_bound`. Previously an absurd value in the darwin branch
passed silently.

**B5 — casefold uniqueness.** Stripping every `.casefold()` from `catalog_service.py` now
**fails** both `test_add_paths_alias_uniqueness_is_casefold` and
`test_rename_rejects_casefold_collision`. Previously it broke nothing. The tests now
exercise a genuine case difference rather than passing on exact equality.

**B6 — toolbar objectName.** `main_window.py:85` sets `primary_toolbar`, and you went
further than asked and named the dock, editor, results tabs, splitter and all five menus.
`QMainWindow.saveState()` now emits no warning, every `QToolBar`/`QDockWidget` has a
non-empty `objectName`, and the state payload grew from 151 to 181 bytes — the toolbar is
genuinely being persisted now. Removing the objectName **fails**
`test_main_window_structure`.

Also noted: the three fixes landed as three properly scoped commits (`a9bd6ce`, `d1db341`,
`1f29727`), correcting round 02's squash. Good.

## Required change

### B7. The session log does not record round 03

`docs/agent_conversations/2026-07-31_pyqt6-catalog-editor-formatter.md` was last modified
in `ff4624c` and ends at the round-02 "B2 correction" section. `AGENTS.md` Section 14
requires the log to cover the work, and Section 15 lists "session log recorded" in the
Definition of Done. This is the last thing between the branch and integration.

Append a round-03 section covering:

1. **B4** — that `Meta+Shift+F` was incorrect on macOS because Qt maps `Ctrl` to Command
   and `Meta` to Control, so the platform branch produced Control+Shift+F; that the branch
   was removed in favour of an unconditional `Ctrl+Shift+F`; and that the previous test was
   a tautology because it recomputed the expected value with the same branch and literals
   as the implementation.
2. **B5** — that `.casefold()` was not covered by any test, that both casefold-named tests
   passed on exact equality alone, and how they were strengthened.
3. **B6** — that the missing toolbar `objectName` silently dropped the toolbar from
   `QMainWindow.saveState()`, and that object names were added across the toolbar, dock,
   editor, results tabs, splitter and menus.
4. **Final tallies** — baseline `107 passed, 1 skipped`; final `179 passed, 1 skipped`.
5. **Deferred/unverified**, carried from the plan's Verification section: no native dialog
   was opened, no real file-manager drag, no real window (all offscreen), macOS and Windows
   unverified — and state explicitly that **the corrected `Cmd+Shift+F` binding itself
   remains unverified on macOS**, since Linux CI cannot exercise it; no query executes; no
   completion or call tips (Phase 7); clipboard assertions use the offscreen platform's
   clipboard, not the system one; CI unproven until first push.

Commit as `docs: close out catalog editor and formatter session log`.

## Mutation results this round

| Finding | Mutation | Before | Now |
|---|---|---|---|
| B4 | change the shortcut literal | no bite (darwin branch never ran on Linux) | **bites** — 2 tests |
| B5 | strip every `.casefold()` | no bite | **bites** — 2 tests |
| B6 | remove toolbar `objectName` | n/a (defect) | **bites** — `test_main_window_structure` |

Tree was clean after every revert.

## Also confirmed

- Streamlit path untouched across the whole branch: `git diff --name-only dev..HEAD` over
  `app.py`, `engines.py`, `ui/`, `export/`, `storage/`, `constants.py` and `.streamlit/`
  is empty.
- Round-01 accepted deviations (`entries` as a property, `add_paths` returning
  `CatalogServiceReport`) remain unchanged, as agreed.

STATUS: CHANGES_REQUESTED
