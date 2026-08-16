# Feature Ideas

**Product:** A local, offline desktop SQL workbench (PyQt6) that lets an analyst point at CSV/Parquet/JSON/Excel files on disk and query them with DuckDB or Spark, with schema inspection, column profiling, SQL completion, dialect translation, and export.

**Primary users (inferred):** A data analyst who keeps working files in a OneDrive/Documents folder and wants SQL over them without loading a database; a data engineer spot-checking Parquet output from a pipeline; an analyst translating SQL between dialects (Oracle/PostgreSQL/DuckDB) before pasting it into a real warehouse.

**Date:** 2026-08-16

## How these were generated

I read `README.md`, `pyproject.toml`, the desktop package (`main_window.py`, `actions.py`, `widgets/`, `models/`, `services/`, `storage/`), and the `SettingsService` key list to establish what actually persists between sessions. I then walked through three imagined sessions: first launch with a folder of Parquet exports, a second-day return to a half-written query, and an hour-100 user with 200 history entries. Friction clustered in three places — nothing about your *work* survives a restart, the catalog and schema panels spend their width on directory prefixes instead of filenames, and the value-counts window silently hides most of what it computes. No competitor context was supplied, so every idea is grounded in this repo.

## Quick wins

### 1. Make the value-counts chart scrollable

- **Value:** ★★★★★  **Effort:** ★★☆☆☆
- **Why this matters:** This is broken by default, not just at the margins. `ValueCountsChart.paintEvent` computes `row_height = max(22, (height - 16) // len(counts))` (`value_counts_window.py:55`), and the default Top N is 50 (`:143`). Fifty rows at the 22px floor is ~1100px of bars painted into a chart pane that's a few hundred pixels tall — and the chart is a bare `QWidget` added straight to the layout (`:158-160`), with no `QScrollArea` anywhere. Everything past the fold is drawn off-widget and is unreachable by any means. A user who opens value counts on a column with 50 distinct values sees maybe the top 8 and has no indication the rest exist.
- **What it looks like:** Wrap `self.chart` in a `QScrollArea` with `setWidgetResizable(True)`. Give `ValueCountsChart` a real `sizeHint()`/`setMinimumHeight()` of `len(counts) * row_height + padding * 2` so the scroll area knows the true content height, and drop the `max(22, …)` compression in favour of a fixed comfortable row height.
- **Code anchor:** `src/wherewolf/desktop/widgets/value_counts_window.py:30-81,158-160`

### 2. Show the filename in the catalog File column

- **Value:** ★★★★★  **Effort:** ★★☆☆☆
- **Why this matters:** `CatalogModel.data` returns the full absolute path (`catalog_model.py:72`), and 0.8.0 only changed the elide direction. Measured against the real dock: at a 450px dock the File section resolves to 190px and *neither* `customers.parquet` nor `transactions_2026_q1.parquet` is visible; you need a ~700px dock. Worse, column 1 is `Stretch` (`catalog_dock.py:55`), which makes it non-draggable — so the user literally cannot widen it. The one column meant to distinguish rows shows the shared prefix they all have in common.
- **What it looks like:** Return `entry.path.name` for `DisplayRole`, keep the full path on the existing `ToolTipRole` (`catalog_model.py:79`), and switch section 1 to `Interactive` with a sensible default width. Optionally add a separate, collapsible "Folder" column for the parent directory.
- **Code anchor:** `src/wherewolf/desktop/models/catalog_model.py:72`, `src/wherewolf/desktop/widgets/catalog_dock.py:50-57`

### 3. Debounce the Top N spinbox

- **Value:** ★★★☆☆  **Effort:** ★☆☆☆☆
- **Why this matters:** `self.limit_selector.valueChanged.connect(self._run_worker)` (`value_counts_window.py:144`) starts a fresh `ValueCountsWorker` thread on *every* value change. Clicking the up-arrow from 50 to 60 launches ten concurrent scans of the column; typing "500" launches three. On a large Parquet file that's a visible stall and a pile of redundant work, and results can land out of order.
- **What it looks like:** Route `valueChanged` through a ~300ms `QTimer` single-shot, and cancel/ignore results from superseded workers.
- **Code anchor:** `src/wherewolf/desktop/widgets/value_counts_window.py:144,165-179`

### 4. Keep the result summary on screen

- **Value:** ★★★☆☆  **Effort:** ★★☆☆☆
- **Why this matters:** Engine, elapsed time, row count and the truncation warning are assembled into a good summary string — then handed to `self._show_status(msg, 10000)` (`main_window.py:623-627`), so it vanishes after ten seconds. A user who runs a query, scrolls the results for a minute, and then wonders "was this truncated? how many rows?" has to re-run it to find out. The truncation flag in particular is a correctness signal that shouldn't be transient.
- **What it looks like:** A thin always-visible label strip above the results table showing `12,481 rows · 0.42s · DuckDB · truncated at 1,000 preview rows`. Keep the status bar message too.
- **Code anchor:** `src/wherewolf/desktop/main_window.py:622-632`, results page assembled at `:892-906`

## Substantial features

### 5. Persist the catalog across sessions

- **Value:** ★★★★★  **Effort:** ★★★☆☆
- **Why this matters:** This is the biggest quality-of-life gap in the product. `CatalogService` has no save or load path, and `storage/` contains only `history.py`. `SettingsService` persists geometry, splitter sizes, fonts, themes, export format, preview limit, and the last dataset *directory* — but not the datasets themselves. So the core loop is: launch the app, re-add the same eight files, re-wait for schema inspection and profiling, then start working. Query history survives; the thing history's queries actually refer to does not, which means restoring a query from history can leave you with SQL referencing aliases that no longer exist.
- **What it looks like:** Serialize catalog entries (path, alias, format) to JSON alongside the history file. On launch, reload them, mark any missing files as unavailable rather than dropping them silently, and lazily re-inspect schemas. v2: named "workspaces" so an analyst can keep a Q1 set and a Q2 set separate.
- **Code anchor:** `src/wherewolf/services/catalog_service.py`, mirroring `src/wherewolf/storage/history.py`

### 6. Don't lose the query I was writing

- **Value:** ★★★★★  **Effort:** ★★★☆☆
- **Why this matters:** Only *executed* queries reach history (`main_window.py:614-620`). A draft you were halfway through — the interesting case, because it's the one you hadn't got working yet — is gone when you close the window. There's also no Open or Save action anywhere in `DesktopActions`, so there's no way to keep a query as a file either. For a tool whose entire purpose is authoring SQL, the authored artifact is the one thing it doesn't look after.
- **What it looks like:** Two parts. (a) Persist the editor buffer on close and restore it on launch, via a new `SettingsService` key. (b) Add `Open SQL…` / `Save SQL…` / `Save As…` actions with the standard shortcuts, and show the current filename in the window title.
- **Code anchor:** `src/wherewolf/desktop/actions.py`, `src/wherewolf/services/settings_service.py`, `src/wherewolf/desktop/main_window.py:258`

### 7. Multiple query tabs

- **Value:** ★★★★☆  **Effort:** ★★★★☆
- **Why this matters:** `self.editor` is a single instance throughout `main_window.py`. Every real analysis session involves more than one query held at once — the working query, the one that built the reference table, the scratch `SELECT DISTINCT` you keep re-running to check a value. Right now the only way to keep a second query is to paste it somewhere outside the app, which is exactly the "I have to leave the app for this" signal. The results side already uses a `QTabWidget` (`:882`), so the pattern is established in the codebase.
- **What it looks like:** A `QTabWidget` of `SqlEditor` instances with Ctrl+T / Ctrl+W, tab labels from the saved filename or first line of SQL, and per-tab results. Pairs naturally with #6 — tabs restore on launch.
- **Code anchor:** `src/wherewolf/desktop/main_window.py` (editor construction and every `self.editor` reference), `src/wherewolf/desktop/widgets/sql_editor.py`

### 8. Search and pin query history

- **Value:** ★★★★☆  **Effort:** ★★☆☆☆
- **Why this matters:** `HistoryDock` enables column sorting (`history_dock.py:70`) but has no filter box. History is the product's memory, and by week three it's hundreds of rows — including every typo'd variant of every query. Sorting by timestamp doesn't help you find "that join I got working on Tuesday". The 0.8.0 work already added multi-select, delete, and save-as-SQL, so the dock is clearly meant to be worked in; search is the missing half.
- **What it looks like:** A filter `QLineEdit` above the table doing substring match over the SQL text (reuse the preview-filter pattern at `main_window.py:911-919`), plus a star/pin toggle and a "pinned only" checkbox so good queries stop scrolling away.
- **Code anchor:** `src/wherewolf/desktop/widgets/history_dock.py`, `src/wherewolf/storage/history.py:76-108`

### 9. Make the schema panel usable on wide tables and long paths

- **Value:** ★★★★☆  **Effort:** ★★☆☆☆
- **Why this matters:** Two problems in one widget. The status label interpolates the full absolute path into a single line (`schema_panel.py:274`) and then appends up to four more clauses (stale, skipped, profiling error, profiling…) onto the same label; it's `setWordWrap(True)`, and Windows paths have almost no spaces to break on, so it wraps badly and pushes the real content down. Separately, there's no way to filter the column list — on a 200-column Parquet file, finding one column means scrolling.
- **What it looks like:** Show `alias — filename.parquet (parquet) — 42 columns` with the full path as a tooltip, and move the warning clauses to their own line or an icon strip. Add a filter box over the column table.
- **Code anchor:** `src/wherewolf/desktop/widgets/schema_panel.py:65-67,264-290`

### 10. Give the value-counts window a splitter, sort, and export

- **Value:** ★★★☆☆  **Effort:** ★★☆☆☆
- **Why this matters:** Beyond the scrolling bug in #1, the window stacks a table and a chart in a fixed `QVBoxLayout` (`:151-160`) with the chart set to `Expanding`, so the two fight for space and neither gets enough. The table isn't sortable, so you can't flip to the *rarest* values — usually the more interesting end when you're hunting data quality problems. And the results can only leave via clipboard TSV; there's no export, even though the app has a full export subsystem.
- **What it looks like:** Put table and chart in a `QSplitter` with persisted sizes, enable sorting on the table, and add an Export button reusing `export_controller`. A "copy chart as image" via `QWidget.grab()` is nearly free.
- **Code anchor:** `src/wherewolf/desktop/widgets/value_counts_window.py:137-163`, `src/wherewolf/desktop/export_controller.py`

## Ambitious bets

### 11. Chart any result set, not just value counts

- **Value:** ★★★★☆  **Effort:** ★★★★☆
- **Why it's ambitious:** It's a new panel with its own state (encoding choices, chart types, persistence) and it edges the product from "SQL workbench" toward "lightweight BI tool" — an identity decision worth making deliberately rather than drifting into.
- **Why this matters:** The moment after a query succeeds, an analyst's next question is usually visual — is this trending, is this distribution what I expect. Today that means Export to CSV, open Excel, chart there. That round trip is the clearest "leaves the app" in the whole product. You already have the two hard pieces: a palette-aware `QPainter` chart widget that respects light/dark theming, and Polars in the result path.
- **What it looks like:** A "Chart" tab beside Results/Messages/Translation. Pick X, Y, and optional series from the result columns; render line/bar/scatter. Reuse and generalize `ValueCountsChart` rather than adding a plotting dependency.
- **Code anchor:** `src/wherewolf/desktop/main_window.py:882-982` (results tab bar), `src/wherewolf/desktop/widgets/value_counts_window.py:30-81`

### 12. A saved-query library with parameters

- **Value:** ★★★★☆  **Effort:** ★★★★☆
- **Why it's ambitious:** Needs a new storage schema, a new dock, a parameter-substitution layer in the execution path, and careful interaction with catalog aliases — which is exactly why it depends on #5 landing first.
- **Why this matters:** History answers "what did I run"; it doesn't answer "what do I run every Monday". An analyst checking the same five quality rules against each week's export currently re-finds them in history and hand-edits the file alias each time. Named, parameterized queries turn the tool from a scratchpad into something with a repeatable workflow — and the pieces are half-present already, since 0.8.0 added "save selected history records as SQL".
- **What it looks like:** A Saved Queries dock. Save the current editor buffer with a name and description; support `:param` placeholders prompted at run time; a `{dataset}` placeholder bound to a catalog entry so the same rule runs against this week's file.
- **Code anchor:** New service alongside `src/wherewolf/services/`, storage alongside `src/wherewolf/storage/history.py`, execution via `services/execution_request_builder.py`

## Ideas considered but cut

- **Run selection / run statement at cursor** — already implemented; `SqlEditor.text_to_run` (`sql_editor.py:352-370`) prefers the selection and otherwise resolves the statement under the cursor.
- **Sortable, filterable results** — already there (`result_table_view.py:36`, preview filter at `main_window.py:911`).
- **Dark mode** — shipped in 0.7.0, with theme-aware palettes throughout.
- **Result set pagination** — the preview-limit control plus "Export Full Results" covers the same need with less machinery.
- **Cloud sync / shared workspaces** — contradicts the local-and-offline identity that's the product's main advantage over a hosted SQL tool.
- **Inferred join suggestions across datasets** — appealing given the schema and profiling data already collected, but the false-positive rate on name-matching alone would make it noise; revisit if profiling ever captures value overlap.
