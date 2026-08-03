# Review — desktop-parity (round 01)

Branch: `feat/desktop-parity` @ `f21eb2b`
Reviewed against: `docs/plans/2026-08-02_desktop-parity.md`

## Verdict

APPROVED.

All eight tasks landed, one commit each, and — the part that actually mattered for this
plan — **every feature is reachable from `MainWindow`**, which is the specific failure
that let the previous round ship two fully-tested dead widgets.

## Reachability, measured by review

I did not read the session log. I constructed a real `MainWindow` offscreen and reached
each feature the way a user would:

```text
D4 edit menu    6 actions: Undo, Redo, Cut, Copy, Paste, Toggle Comment
D5 contrast     min luminance delta 0.45
                (default=0.71 identifier=0.71 operator=0.71 keyword=0.45 number=0.66)
D3 schema panel SchemaPanel, reachable via MainWindow.schema_panel
D2 translation  tabs: ['Results', 'Messages', 'Translation']
D6 controls     engine_selector, input_dialect_selector, export_format_selector,
                editor_theme_selector, translation_target_selector,
                preview_limit_selector (10-1000, default 100)
```

`grep` confirms `SchemaPanel` and `TranslationPanel` are now imported by
`desktop/main_window.py` rather than by tests alone. The preview default is back to
Streamlit's 100, down from the hardcoded 1000.

## Behaviour, not just widget existence

Existence of a combobox proves nothing, so I exercised the paths:

```text
azure sql transpiled   'SELECT TOP 3 id FROM t' -> 'SELECT\n  id\nFROM t\nLIMIT 3'
autofill (empty)       'SELECT * FROM data LIMIT 10'
autofill (user text)   '-- my work'  (preserved, not clobbered)
preview limit          reaches ExecutionRequest.preview_limit = 37
translation panel      tsql -> duckdb / spark / postgres all render real transpiled SQL
translation targets     33 dialects, taken from sqlglot rather than a hand-kept list
```

`TOP 3` becoming `LIMIT 3` is a genuine dialect conversion, not a passthrough.

## Negative controls

The plan required proof the new tests can fail. I mutated the implementation three ways
and confirmed each guard bites:

| mutation | result |
|---|---|
| `edit_menu.addAction(...)` → `pass` | `tests/test_main_window.py` 1 failed, 31 passed |
| `lexer.setColor/setPaper` → no-op | `tests/test_sql_editor.py` 1 failed, 16 passed |
| auto-fill guard → `if True:` | `tests/test_main_window.py` 1 failed, 31 passed |

Each mutation fails exactly one test and leaves the rest green, so the guards are
targeted rather than incidental. Working tree restored clean afterwards.

## Gates

```text
ruff check          All checks passed
ruff format --check 141 files already formatted
ty check src/       All checks passed
pytest              367 passed, 7 deselected   (was 356; +11 tests)
git status --short  clean
```

The `pyarrow` import at `execution/registry.py:23` survives untouched, as required.

## The boundary held

No version bump, no tag, no `main` change. Version still `0.5.2`.

## What this does not cover

The colour scheme is verified by computed luminance, not by looking good; panel layout
and native dialog behaviour remain manual maintainer checks. macOS and Windows are still
only covered by the offscreen `qt-smoke` job.

**Known gaps deliberately left for follow-up work** (audited this session, tracked
separately): export warnings computed but never displayed, `DontConfirmOverwrite` on the
export dialog, Find/Replace/Select All and preview filtering built but unreachable, no
Preferences UI, missing empty states and Run gating, and Spark availability keyed only on
`find_spec("pyspark")` rather than a real Java runtime.

STATUS: APPROVED
