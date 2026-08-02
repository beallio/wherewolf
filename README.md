# Wherewolf

<img src="https://raw.githubusercontent.com/beallio/wherewolf/main/src/wherewolf/assets/img/wherewolf_banner.png?cacheBuster=21" width="100%">

[![CI](https://github.com/beallio/wherewolf/actions/workflows/ci.yml/badge.svg?cacheBuster=21)](https://github.com/beallio/wherewolf/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/wherewolf.svg?cacheBuster=21)](https://pypi.org/project/wherewolf/)
[![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-blue.svg?cacheBuster=21)](https://www.gnu.org/licenses/gpl-3.0.html)

Wherewolf is a local SQL workbench for CSV, Parquet, JSON, JSON Lines, and XLSX files. It opens
a native PyQt6 desktop window and runs queries with DuckDB by default. There is no browser UI and
no local web server.

![Wherewolf Screenshot](https://raw.githubusercontent.com/beallio/wherewolf/main/src/wherewolf/assets/img/screenshot.png?cacheBuster=21)

## Install

Wherewolf requires Python 3.12 or newer.

```bash
uv tool install wherewolf
wherewolf
```

`wherewolf-desktop` is an equivalent entry point. Both commands open the native desktop window.

### Optional Spark engine

The default installation is DuckDB-only: it neither installs nor imports PySpark. To enable the
local Spark engine, install the extra and a Java runtime compatible with PySpark (CI uses Java
21):

```bash
uv tool install 'wherewolf[spark]'
```

Spark runs locally as `local[1]` with bounded driver memory. It is not a remote- or cluster-Spark
client.

### From source

```bash
git clone https://github.com/beallio/wherewolf.git
cd wherewolf
./run.sh uv sync
./run.sh uv run wherewolf
```

For the optional Spark engine from a source checkout, run `./run.sh uv sync --extra spark` after
installing Java.

## Desktop workflow

1. Choose **Add Datasets…** or drag supported local files into the Dataset Catalog. The command
   opens the operating system's native multi-file dialog where Qt supports it.
2. Each file receives a table alias. Rename it from the catalog context menu when needed, then
   use the alias in SQL. The Schema dock reports discovered columns and any schema error.
3. Write SQL in the editor and press **Ctrl+Return** to run the selection or current statement.
   **Ctrl+Space** opens completion, and **Ctrl+Shift+F** formats SQL. On macOS, use the platform's
   equivalent shortcut conventions.
4. Press **Ctrl+.** to request cancellation of the active query. The status bar and Messages tab
   report state, timing, preview rows, truncation, and errors.
5. History records successful queries in `~/.wherewolf/history.json`. Selecting a history entry
   restores its SQL and available datasets without immediately running it. Use **File → Clear
   History** to remove saved entries or **View → Reset Layout** to restore the default layout.

Window geometry, docks, splitter proportions, editor font size, recent dataset directory, and
completion preferences are persisted between desktop sessions.

## Results grid and ordering

The grid displays a bounded preview (up to 1,000 rows), preserves values for typed sorting, and
supports selection, spreadsheet-compatible TSV copy, search/filtering, column reordering,
hiding, auto-sizing, and reset. Right-click a header to copy or insert its name, adjust columns,
or choose an ordering action.

Clicking a header only sorts the local preview. While a local sort is active, Wherewolf labels it
**Sorted preview only.** It does not rerun or alter your query. To change the result order of the
query itself, use **Apply Ascending Order to Query** or **Apply Descending Order to Query** from
that header's context menu, then run the resulting SQL.

## Export

**Export Preview…** writes the currently displayed, bounded preview. **Export Full Results…**
re-executes the captured query rather than exporting only the preview. For DuckDB, full CSV and
Parquet exports stream directly to disk without materializing the entire result in Python; full
XLSX export is intentionally capped at 100,000 rows. The desktop export action currently selects
CSV destinations. Spark has no desktop full-export adapter, so full Spark export is not available.

## License

Wherewolf is licensed under **GPL-3.0-only**. Releases through 0.5.2 remain available under MIT;
their original text is retained in `LICENSES/MIT-pre-0.6.txt`, and those prior grants remain
valid.

## Development

Run the test suite from a source checkout:

```bash
./run.sh uv run pytest
```

The project uses `uv`, `ruff`, and `ty`; see [AGENTS.md](AGENTS.md) for the project execution and
cache-isolation contract.
