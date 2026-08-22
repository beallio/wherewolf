# Feature Ideas

**Product:** Wherewolf is a local, native PyQt6 SQL workbench that points DuckDB (optionally local Spark) at CSV/Parquet/JSON/XLSX files on disk — no server, no browser, no cloud.
**Primary users (inferred):** a data analyst poking at an ad-hoc export someone emailed them; a data engineer sanity-checking Parquet output from a pipeline; an analytics engineer iterating on a transform they'll later port to dbt/Spark; a non-SQL-native ops person running a saved, parameterised data-quality query each week.
**Date:** 2026-08-21

## How these were generated

Read the README, CHANGELOG through 0.10.0, the CLI, the DuckDB engine's view registration, the catalog service, the settings surface, and the desktop action/widget inventory. The previous report (`feature-ideation-ui-quality-of-life.md`) has essentially all shipped — tabs, catalog persistence, saved queries, history search — so this pass deliberately looks past UI polish at the two places friction now concentrates: **what you can point Wherewolf at** (one file, one alias, auto-detected settings, no folders) and **what you can do after a query returns** (a bounded preview you can only look at, not build on). Friction below is imagined from those code paths, not reported by users.

## Quick wins

### 1. Selection statistics in the status bar

- **Value:** ★★★★★  **Effort:** ★☆☆☆☆
- **Why this matters:** Every analyst arrives from Excel, where dragging over a column of numbers shows sum/average/count for free. In Wherewolf the same instinct requires editing the SQL, re-running, and losing your place. It is the single most-used feature of a spreadsheet and it is absent.
- **What it looks like:** On selection change in the results grid, show `Count: 412  Sum: 88,190.42  Avg: 213.57  Min/Max: …` in the status bar for numeric selections; count and distinct-count for non-numeric. Computed on the already-materialised preview frame, so it's free.
- **Code anchor:** `desktop/widgets/result_table_view.py` already tracks typed values and has `selection_for_export()`; add a `selection_stats_changed` signal beside `local_sort_changed` and render it near `_set_result_summary` in `desktop/main_window.py`.

### 2. "Count all rows" beside the truncation notice

- **Value:** ★★★★☆  **Effort:** ★☆☆☆☆
- **Why this matters:** The preview caps at 1,000 rows and says so, which immediately raises the question it doesn't answer: how many rows are there really? Right now the user hand-wraps their own query in `SELECT count(*) FROM (…)` — a mechanical edit that also blows away the result they were looking at.
- **What it looks like:** A link/button in the truncation notice that runs `SELECT count(*) FROM (<captured query>)` against the stored request and replaces "1,000 rows (truncated)" with "1,000 of 4,812,331 rows". Uses the captured `ExecutionRequest`, so parameters bind identically.
- **Code anchor:** `_EditorTabState.last_request` in `desktop/main_window.py:112`; the same request path `Export Full Results…` already re-executes.

### 3. Jump to the error position in the editor

- **Value:** ★★★★☆  **Effort:** ★★☆☆☆
- **Why this matters:** 0.8.0 made failures visible by raising the Messages tab in red — good — but the user still reads a character offset out of DuckDB's message and finds the spot by eye. On a 60-line query with three CTEs, "syntax error at or near ..." is a scavenger hunt, and it's the most repeated moment in the core loop.
- **What it looks like:** Parse the position DuckDB/sqlglot reports, then place the caret there and mark the line with a QScintilla indicator. Clicking the error line in Messages jumps to it too.
- **Code anchor:** `desktop/widgets/messages_panel.py` for the click source; `desktop/widgets/sql_editor.py` already carries diagnostic plumbing via `diagnostics_reported`.

### 4. Cell value inspector

- **Value:** ★★★★☆  **Effort:** ★★☆☆☆
- **Why this matters:** JSON files are a first-class source, so nested structs and long strings land in cells routinely — and a grid row shows the first ~40 characters of a 4KB JSON blob with no way to see the rest. The user copies the cell out to a text editor to read it, which is the "I have to leave the app for this" tell.
- **What it looks like:** A collapsible detail pane (or `Ctrl+Shift+I` popup) showing the focused cell's full value, pretty-printed when it parses as JSON, wrapped when it's text, with its own copy button.
- **Code anchor:** New widget under `desktop/widgets/`, fed by the current index of `result_table_view`; reuse `desktop/clipboard_serializers.py:format_cell_value` for rendering.

## Substantial features

### 5. Save a result as a dataset

- **Value:** ★★★★★  **Effort:** ★★☆☆☆
- **Why this matters:** Real analysis is a chain: clean, then aggregate, then join to a lookup. Wherewolf makes step one disposable — the result exists only as a preview, so step two means wrapping step one in a subquery or CTE and re-reading the source file every time. Meanwhile the DuckDB engine holds a **persistent in-memory connection** across queries, so the capability is already sitting there unexposed.
- **What it looks like:** "Save Result as Dataset…" on the results pane creates `CREATE OR REPLACE TABLE <alias> AS <captured query>` and adds a derived entry to the catalog, badged as derived (with its defining SQL on hover) and rebuildable on demand. Derived entries are session-scoped unless the user materialises them to Parquet.
- **Code anchor:** `execution/duckdb_engine.py` (`self.con` is already long-lived and `_register_view` already owns the alias namespace); `services/catalog_service.py` for a new derived-entry kind.

### 6. Folder and glob datasets

- **Value:** ★★★★★  **Effort:** ★★★☆☆
- **Why this matters:** `_register_view` maps exactly one file to one alias, but the data engineer's Parquet almost never arrives as one file — it arrives as `export/date=2026-08-01/part-*.parquet`. Today they add 30 files, get 30 aliases, and hand-write a 30-way `UNION ALL`, or give up and go to the DuckDB CLI. DuckDB does this natively in one call.
- **What it looks like:** "Add Folder…" and a glob field in the catalog. One alias backed by `read_parquet('dir/**/*.parquet', hive_partitioning=true)`, showing file count and partition columns in the Schema dock. Same for CSV/JSON globs.
- **Code anchor:** `execution/duckdb_engine.py:_register_view`; `domain/models.py` `CatalogEntry` gains a pattern alongside `path`; `storage/catalog.py` persists it.

### 7. Import options for messy files

- **Value:** ★★★★☆  **Effort:** ★★★☆☆
- **Why this matters:** Everything goes through `from_csv_auto`, which is excellent right up until it isn't: a semicolon-delimited European export, a latin-1 file, two junk preamble rows above the header, `NULL`/`N/A` sentinels, or a ZIP-code column DuckDB decides is an integer. Each of those is a hard stop with no recourse inside the app — the user leaves to clean the file, which is the workflow Wherewolf exists to remove.
- **What it looks like:** An "Import Options…" dialog per catalog entry — delimiter, quote, encoding, skip rows, header on/off, null strings, per-column type override, and sheet name for XLSX — persisted with the catalog entry and applied on re-registration. Defaults stay fully automatic.
- **Code anchor:** `execution/duckdb_engine.py:_register_view` (swap `from_csv_auto` for parameterised `read_csv`); options stored on `CatalogEntry` in `domain/models.py` and `storage/catalog.py`.

### 8. Page through the full result

- **Value:** ★★★★☆  **Effort:** ★★★☆☆
- **Why this matters:** The preview cap is a memory guard, but users read it as "this is all you get." Wanting row 5,000 currently means either raising the cap to 100,000 and paying for it on every query, or adding `OFFSET` by hand. The stored request makes a windowed re-query cheap and honest.
- **What it looks like:** Next/Previous page controls beside the grid that re-run the captured request with `LIMIT n OFFSET k` (with a stable ordering warning when the query has no `ORDER BY`, since offset without order is not a stable window).
- **Code anchor:** `services/execution_request_builder.py` and the `_EditorTabState.last_request` re-execution path; reuse the `Export Full Results…` machinery.

### 9. Run the whole script, not just one statement

- **Value:** ★★★★☆  **Effort:** ★★★☆☆
- **Why this matters:** `services/statement_service.py` already splits a buffer into statements with quote/comment awareness — the hard part is done — but Ctrl+Return runs exactly one. A file that sets up two views and then queries them (exactly what an analytics engineer keeps in a `.sql` file, and `.sql` files are openable now) has to be executed by hand, statement by statement, in order.
- **What it looks like:** "Run Script" (`Ctrl+Shift+Return`) executes every statement in order, stops at the first failure, and prints per-statement timing to Messages. The last result-producing statement fills the grid.
- **Code anchor:** `services/statement_service.py:split_statements`; new action in `desktop/actions.py`; sequential dispatch in the existing execution worker.

### 10. Headless query mode in the CLI

- **Value:** ★★★★☆  **Effort:** ★★★☆☆
- **Why this matters:** `--version` was deliberately built to answer without loading Qt "so it works over SSH" — the instinct is already in the codebase. The same engine that powers the window could answer `wherewolf query` on a box with no display, which turns a GUI tool into something that also runs in a Makefile, a cron job, or a CI check. It also makes a saved data-quality query schedulable instead of a thing someone remembers to click.
- **What it looks like:** `wherewolf query "SELECT …" --dataset sales=sales.parquet --format csv -o out.csv`, plus `wherewolf run --saved "Weekly nulls" --param week=2026-W34`. No Qt import on this path.
- **Code anchor:** `cli.py` already dispatches subcommands before touching Qt; `execution/registry.py`, `storage/saved_queries.py`, and `services/preview_export.py` are all GUI-free.

## Ambitious bets

### 11. Attach local databases

- **Value:** ★★★★☆  **Effort:** ★★★★☆
- **Why it's ambitious:** It widens the product's noun from "files" to "local data", which touches the catalog model (a database contributes many tables, not one alias), the schema dock, completion, and persistence — and invites the follow-on question of remote connections, which the product has so far correctly refused.
- **Why this matters:** A `.duckdb` or `.sqlite` file is exactly the kind of thing that already sits in the same folder as the CSVs a user is querying — an app's local database, a previous DuckDB session's output, a Core Data or Firefox store. DuckDB's `ATTACH` reads both today. Being able to join last month's Parquet export against the SQLite table it came from is a genuinely new capability, not parity.
- **What it looks like:** "Attach Database…" adds a catalog node that expands to its tables; queries reference `db.table`; the Schema dock and completion treat attached tables like any other source. Read-only by default.
- **Code anchor:** `execution/duckdb_engine.py` (`ATTACH … (READ_ONLY)`); `services/catalog_service.py` and `desktop/models/catalog_model.py` grow a two-level node.

### 12. Workspaces

- **Value:** ★★★★☆  **Effort:** ★★★★☆
- **Why it's ambitious:** Every persisted thing today is global and singular — one catalog, one tab set, one history in `~/.wherewolf/`. Making those plural means a scoping decision across `settings_service`, `storage/catalog.py`, `storage/history.py`, and `storage/saved_queries.py`, plus migration of existing state into a default workspace.
- **Why this matters:** 0.9.0 made state survive restart, which was right — but it also means a user with two concurrent analyses has both piled into one catalog and one tab strip. A consultant or anyone with more than one client is now fighting the persistence that was supposed to help them, and there is no way to hand a colleague "the setup for this analysis."
- **What it looks like:** A `.wherewolf` workspace file capturing catalog entries (relative paths where possible), open tabs, saved queries, and layout. File → Open/Save Workspace, recent workspaces, and window-title identification. Checked into a repo, it's a shareable analysis.
- **Code anchor:** New `storage/workspace.py`; scope keys in `services/settings_service.py`; the existing `save_editor_tabs`/`restore_editor_tabs` and catalog snapshot APIs are the serialisation primitives.

## Ideas considered but cut

- **Chart any result set** — still the strongest unshipped idea from the previous report; deliberately not re-argued here rather than cut on merit. The value-counts window already proves the `QPainter` approach works without a plotting dependency.
- **Natural-language → SQL.** The catalog schemas would ground it well, but every credible implementation sends the user's schema to a remote API, which contradicts the "no server, local files" identity the README leads with. Revisit only for a fully local model.
- **S3/HTTPS sources via `httpfs`.** Technically a small change; strategically it pulls in credentials, profiles, and cost surprises, and blurs the local-first promise.
- **Result diffing between two tabs.** Genuinely useful for "did the pipeline change?", but expensive to do well (key inference, tolerance for float noise) and narrower than it first appears.
- **Command palette.** The action inventory is small enough that the menus still work; revisit past ~50 actions.
- **Join suggestions from matching column names.** Cute, and the schemas are already loaded — but likely to be wrong often enough to be noise rather than help.

## Two defects noticed while reading (not features) — both fixed in 0.10.1

- `.jsonl` passes `SourceFormat.from_path` (`domain/enums.py`) and appears in the file dialog filter, but `execution/duckdb_engine.py:_register_view` has no `.jsonl` branch, so JSON Lines files fall through to `from_csv_auto` and are parsed as CSV. The README advertises JSON Lines support.
- `constants.py:SUPPORTED_EXTENSIONS` is referenced only by `tests/test_constants.py` — nothing in the app reads it — and it disagrees with the real gate: it lists `.xls` (which `SourceFormat.from_path` rejects) and omits `.jsonl` (which it accepts).
