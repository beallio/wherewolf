# UI refinements implementation session

Date: 2026-08-02
Objective: Implement `docs/plans/2026-08-02_ui-refinements.md` on `feat/ui-refinements`.

## Files and commits

The round is represented by the plan and these atomic implementation commits:

- `2b29fed` moved the editor theme selector from the toolbar to Preferences while
  preserving the existing settings key and default.
- `88f473f` enabled chronological history sorting with a visible timestamp sort indicator.
- `685b12e` added individual dock toggle actions to the View menu.
- `b8c629e` enabled alternating row colours for catalog and schema/profile tables.
- `af86874` added runtime-generated dtype icons and full dtype header tooltips to result
  columns. Files: `polars_table_model.py`, `result_table_view.py`, and
  `tests/test_result_table_view.py`.
- `09cdbfb` moved export controls beside the preview filter, added Preview/Full/Selection
  scope selection and the results-local Export button, and retained Query-menu actions.
- `deb70dd` added DuckDB-backed SQL predicates and inline non-blocking filter errors.
- This session log records the durable evidence for the round.

The pre-existing untracked `feature-ideation-workbench-depth.md` was preserved and is not
part of this round.

## Verification evidence

1. Theme placement: before the move, `editor_theme_selector` was created in the query
   controls toolbar; after the move, the toolbar carries only Run, Cancel, Format SQL and
   Add Datasets, while Preferences owns the selector. The settings round-trip test saved
   `Light` and restored/applied `Light` through the unchanged settings key.
2. History sorting: the timestamp header is sortable and defaults newest-first. The history
   tests exercise timestamp values whose ISO display order differs from chronological
   instants, then verify the order reverses after the header click.
3. Dock restore: the history dock is visible, then hidden by close, then visible again after
   triggering its `History` View-menu toggle action; the catalog sibling remains visible.
4. Alternating rows: history, catalog and schema/profile tables all report
   `alternatingRowColors() == True`. The checks compare the active palette's alternate base
   colour against text luminance rather than hardcoding a theme colour.
5. Result dtype indicators: an integer/string/date/boolean frame produces four non-null,
   distinct runtime icons. Header tooltips include `Int64`, `String`, `Date`, and `Boolean`.
6. Export placement: at 1024px the preview filter, format selector, scope selector, Export
   button and three results-local action buttons are visible; the three QAction instances
   remain in the Query menu and are absent from the primary toolbar. Pressing Export with
   Parquet and Preview selected writes a readable artifact with rows `{"id": 1}` and
   `{"id": 2}`.
7. Preview filtering: `age > 40` returns two rows, `East` still uses substring matching and
   returns two rows, malformed `age >` leaves the two previous rows visible and shows an
   inline error, and `missing_column = 1` leaves the rows visible while naming the missing
   predicate in the error.

## Quality results

- Baseline before Tasks 5–7: 424 tests passed.
- Task 5 targeted verification: 13 tests passed.
- Task 6 targeted verification: 57 tests passed.
- Task 7 focused verification: 62 tests passed.
- Final commit-hook suite: 428 tests passed, 7 deselected.
- Commit hooks passed ruff, ruff format, `ty`, pytest, and the protocol checks.
- All project commands used `./run.sh`; caches and the environment stayed under
  `/tmp/wherewolf`.

## Design decisions

- Header icons are generated as palette-coloured `QPixmap` instances at runtime and exposed
  through the existing model header roles; no asset files were added.
- Export scope is explicit in the results section so the new Export button has deterministic
  Preview, Full results, and Selection behaviour. Existing export actions remain shared by
  the Query menu and results-local buttons.
- SQL predicates run against the current preview frame only. A predicate failure is treated
  as an inline user error when it contains predicate syntax; otherwise the input falls back
  to the existing case-insensitive substring filter. Failed predicates never replace the
  active row mask.
