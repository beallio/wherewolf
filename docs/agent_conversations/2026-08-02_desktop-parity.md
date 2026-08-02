# Desktop parity implementation session

- Date: 2026-08-02
- Task objective: Implement `docs/plans/2026-08-02_desktop-parity.md` on `feat/desktop-parity`.
- Files modified: desktop main window/editor, settings and execution-request services, translator,
  focused main-window/editor/settings tests, and the maintainer-owned manual acceptance checklist.
- Tests added: reachable MainWindow tests for Edit actions, contrast, schema, translation, input
  dialect execution, export artifacts, preview/theme persistence, and first-dataset starter SQL.

## Design decisions

- Reused editor-owned actions in the menubar so shortcuts and enablement cannot drift.
- Used `sqlglot.dialects.DIALECT_MODULE_NAMES` for translation targets.
- Put Schema beside the Dataset Catalog as a tabified dock and Translation beside Results/Messages.
- Kept the two visual controls persisted through `SettingsService`; editor themes supply explicit
  lexer colours for all styles.

## Automated verification

`./run.sh uv run ruff check .`, `./run.sh uv run ruff format --check .`,
`./run.sh uv run ty check src/`, and `./run.sh uv run pytest` passed. Final full suite:
367 passed, 7 deselected.

Focused proof output:

```text
edit-menu: 6 ['Undo', 'Redo', 'Cut', 'Copy', 'Paste', 'Toggle Comment']
contrast-luminance: [0.6584, 0.6584, 0.6584, 0.3061, 0.5679, 0.3473] caret=0.0160
translation: 'SELECT\n  COALESCE(value, 0)\nFROM users'
source-dialect: 'SELECT\n  *\nFROM users\nLIMIT 10'
export: result.parquet rows=2; result.xlsx rows=2
preview-limit: 250
starter: 'SELECT * FROM "select" LIMIT 10'; existing: 'SELECT user_query'
schema-panel: verified by test_main_window_schema_panel_shows_schema_after_adding_dataset: id BIGINT, name VARCHAR
```

Negative controls were run after temporarily reintroducing each defect:

```text
task1 Edit menu: test_main_window_edit_menu_exposes_the_editor_actions failed with assert []
task2 contrast: test_sql_editor_text_lexer_styles_contrast_with_caret_line failed with ratios below 4.5
task8 starter query: test_main_window_fills_starter_query_for_first_dataset_when_editor_is_empty failed with editor text == ''
```

## Deferred manual checks

Native appearance of the colour scheme, native dialog behaviour, and the feel of the Schema and
Translation panels remain maintainer checks in `docs/review/manual-acceptance-checklist.md`.
