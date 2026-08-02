# Post-release-candidate defects

Date: 2026-08-02
Branch: `fix/post-rc-defects` off `dev`

Source: maintainer report (`fix/` directory) after running the installed desktop app.

## Problem Definition

Six defects, one of which is a hard crash on the primary user path.

### D1 — SIGSEGV converting a DuckDB relation to Polars on a worker thread

`fix/error.txt` is a `coredumpctl` dump of the installed app, SIGSEGV. Faulting stack,
innermost first:

```
mi_thread_init
_mi_malloc_generic
arrow::...::SchemaExporter::Finish
arrow::ExportSchema
pyarrow lib Schema._export_to_c
polars_python::interop::arrow::to_rust::field_to_rust_arrow
PyDataFrame::from_arrow_record_batches
duckdb::DuckDBPyRelation::ToPolars
sipQThread::run
```

The main thread was idle in `QEventLoop::exec` — this is **not** a shutdown race and
**not** the posted-event-to-freed-QObject bug fixed earlier.

**Root cause, established by bisection (see Testing Strategy):** `libarrow.so` is
dlopened lazily by DuckDB during the first `.pl()` call. When that first call happens on
a *secondary* thread, pyarrow's bundled mimalloc initialises its thread-local heap in
that thread. Once that thread exits, `mi_thread_init` faults for every subsequent
thread. The app creates one fresh `QThread` per query, so the **second** query crashes.

Measured matrix (30 runs each unless noted):

| mode | result |
|---|---|
| all `.pl()` on the main thread | clean |
| one long-lived worker thread, 5 sequential `.pl()` | clean |
| fresh `threading.Thread` per `.pl()` | **SIGSEGV on run 2** |
| fresh `QThread` per `.pl()` | **SIGSEGV on run 2** |
| fresh `QThread` per `.pl()`, bare `import pyarrow` on main thread first | clean |
| fresh `threading.Thread` per `.pl()`, bare `import pyarrow` first | clean |

Qt is incidental: plain `threading.Thread` reproduces it. A bare `import pyarrow` on the
main thread is sufficient; touching the allocator is not required.

**Fix:** import `pyarrow` eagerly at `wherewolf.execution.registry` module scope, which
is imported on the main thread at startup. `pyarrow>=24.0.0` is already a declared direct
dependency (`pyproject.toml:14`), so the import is unconditional.

### D2 — `TranslationPanel` is dead code

`desktop/widgets/translation_panel.py` and `services/translation_view_model.py` exist but
are imported nowhere. `main_window.py:372` builds only Results and Messages tabs. There is
no way to see SQL translated between dialects, which Streamlit offered at
`9212309^:src/wherewolf/ui/results.py:42-71`. `sqlglot.transpile` is still live at
`translation/translator.py:33`.

### D3 — `SchemaPanel` is dead code

`desktop/widgets/schema_panel.py` renders columns but `MainWindow` never constructs it.
`models/catalog_model.py:25` exposes only a "Schema status" column, so the catalog dock
shows Alias/File/Format and nothing else. Streamlit rendered per-alias columns and types
at `9212309^:src/wherewolf/app.py:263-303`.

### D4 — Edit menu is empty

`main_window.py:449-450` creates the Edit menu and adds zero actions. The editor already
owns `_undo_action`, `_redo_action`, `_cut_action`, `_copy_action`, `_paste_action` and
`_toggle_comment_action` (`sql_editor.py:129-150`) for its context menu; the menubar
simply never receives them. Existing tests assert the menu *object* exists, not that it
has actions — that guard is why this shipped.

### D5 — Editor text is invisible

`fix/Screenshot_20260802_102359.png` shows `SELECT  FROM   LIMIT 10`: keywords render
blue and the numeric literal green, but `*` and the table identifier are invisible.
`sql_editor.py:116` hardcodes `setCaretLineBackgroundColor(QColor("#f5f5f5"))` — a
near-white caret line — while the editor paper follows the desktop's dark palette and
`QsciLexerSQL` is never given explicit colours. Styles with no explicit colour (default,
identifier, operator) render light-on-light.

### D6 — Remaining Streamlit parity gaps

Verified against the pre-cutover tree (Streamlit was deleted in `9212309`):

| gap | Streamlit source | desktop state |
|---|---|---|
| input-dialect selector + transpile before run | `app.py:371-413` | absent; `main_window.py:195` hardcodes duckdb/spark |
| export-format chooser (CSV/Excel/Parquet) | `ui/results.py:88-108` | absent; `main_window.py:273` always CSV |
| preview-size control (10–1000, default 100) | `app.py:310` | absent; fixed at 1000 in `execution_request_builder.py:21` |
| editor-theme selector | `app.py:332-363` | absent; only font size persists |
| "show hidden files" toggle | `ui/file_browser.py:74-100` | absent (native dialog only) |
| auto-fill `SELECT * FROM <alias> LIMIT 10` | `app.py:229-235` | absent |

## Architecture Overview

D1 is a one-line import-ordering fix in the execution layer. D2–D6 are all UI wiring in
`desktop/`, reusing services that already exist and are already unit-tested. No new
architectural layer is introduced.

## Core Data Structures

No new domain types for D1, D4, D5. D2/D3 consume the existing `TranslationViewModel` and
schema results. D6 extends `ExecutionRequest` construction only through existing fields
(`source_dialect`, `preview_limit`) and `ExportFormat`, all of which already exist.

## Public Interfaces

- `wherewolf.execution.registry` gains a module-scope `import pyarrow` with a comment
  recording why it must not be removed or made lazy.
- `MainWindow` gains the translation and schema panels and a populated Edit menu.
- No change to `ExecutionEngine`, `QueryResult`, or the CLI entry points.

## Dependency Requirements

None added. `pyarrow>=24.0.0` is already declared.

## Testing Strategy

**D1** is a native crash, so the guard must be a subprocess exit-code test: spawn a child
that imports the app's execution registry and then runs several *sequential fresh
threads* each doing a DuckDB→Polars conversion, and assert the child exits 0. Before the
fix the child dies with SIGSEGV (-11); after it, exit 0. The negative control is removing
the eager import and confirming the test fails — a test that cannot fail is worthless
here, which is precisely how the earlier export-streaming criterion slipped through.

The run count must exceed 2, since the crash lands on the second thread.

**D4** needs a guard asserting the Edit menu has a non-empty action list, not that the
menu exists.

**D5** needs a test asserting the caret-line background and the lexer's default/identifier
foreground are not both light — i.e. an actual contrast assertion, not a colour literal.

**D2/D3/D6** need tests asserting the widgets are reachable from `MainWindow` and that the
user-visible control changes real request/export state.
