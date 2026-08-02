# Wherewolf

<img src="https://raw.githubusercontent.com/beallio/wherewolf/main/src/wherewolf/assets/img/wherewolf_banner.png?cacheBuster=20" width="100%">

[![CI](https://github.com/beallio/wherewolf/actions/workflows/ci.yml/badge.svg?cacheBuster=20)](https://github.com/beallio/wherewolf/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/wherewolf.svg?cacheBuster=20)](https://pypi.org/project/wherewolf/)
[![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-blue.svg?cacheBuster=20)](https://www.gnu.org/licenses/gpl-3.0.html)

A production-grade, local SQL workbench for querying files (CSV, Parquet, JSON) using DuckDB or Spark.

## Features
- **Multi-Engine Support:** Execute SQL via DuckDB (default) or the optional, memory-bounded local Spark engine (`local[1]`). Native support for CSV, Parquet, JSON, JSON Lines, and Excel (`.xlsx`, `.xls`).
- **📁 Dataset Catalog:** Improved catalog in the desktop shell with native dialogs and drag-and-drop file intake.
- **🧰 Desktop SQL Editor:** QScintilla-based editor with line numbers, brace matching, SQL formatting, function call tips, and intelligent SQL completion (`Ctrl+Space` shortcut and configurable auto-trigger threshold).
- **🔢 PyQt6 Result Grid:** High-performance tabular results view powered by Polars, with strict type preservation (`UserRole`), typed sorting (`TypedSortProxyModel`), case-insensitive multi-column search filtering, visual column reordering and hiding, and TSV clipboard serialization (`Ctrl+C`, custom context menus).
- **🔗 Multi-Table Queries:** Perform JOINs, unions, and subqueries across different file formats in a single session.
- **📊 Schema Panel HUD:** Dedicated dock widget displaying columns, data types, pending schema inspection states, error details, and double-click column identifier insertion.
- **🌐 Translation Panel:** Multi-statement SQL dialect translation (DuckDB <-> SparkSQL) with diagnostic message views.
- **💬 Messages Panel:** Structured execution results, detailed metrics (duration, preview row counts), and formatted error tracebacks replacing raw text placeholders.
- **🔀 Full-Query Ordering:** Context menu actions for applying ascending or descending `ORDER BY` clauses to full queries without disturbing local table proxy sorting.
- **Safe Preview:** Scrollable results limited to 1000 rows.
- **Versioned Query History:** Persists the newest 100 queries in `~/.wherewolf/history.json`,
  automatically migrates prior history safely, and keeps each record's stable ID for unambiguous
  desktop selection.
- **Persistent Desktop Preferences:** Window geometry, dock layout, splitter proportions, editor
  font size, recent dataset directory, and completion preferences survive desktop restarts.
- **Export:** The desktop shell exports the preview (bounded by the preview limit) to CSV, XLSX, or Parquet. Full CSV and Parquet export re-executes the captured query and streams through DuckDB directly to disk; it does not materialize the complete result in Python. Full XLSX is intentionally limited to 100,000 rows because XLSX has no streaming writer; choose CSV or Parquet for larger results.
- **Execution Metrics:** Tracks row count, status, and execution time in the status bar and Messages panel.

![Wherewolf Screenshot](https://raw.githubusercontent.com/beallio/wherewolf/main/src/wherewolf/assets/img/screenshot.png?cacheBuster=20)

## Installation

Ensure you have Python 3.12+ and [uv](https://github.com/astral-sh/uv) installed.

### From PyPI (Recommended)
```bash
uv tool install wherewolf
wherewolf
```

### Optional Spark engine

The default installation is DuckDB-only and does not install or import PySpark. To use Spark,
install the optional extra and a compatible Java runtime:

```bash
pip install 'wherewolf[spark]'
```

From a source checkout, use `uv sync --extra spark`. The desktop engine selector reports this
requirement and leaves Spark unavailable until it is installed. Spark integration is verified on
Linux with one JDK only; other JDK versions, macOS, Windows, and cluster/remote Spark are
unverified.

### From Source
```bash
git clone https://github.com/beallio/wherewolf.git
cd wherewolf
uv sync
```

## Usage
`wherewolf` now opens the native Qt desktop window. `wherewolf-desktop` remains an equivalent
alias for existing invocations. This is a breaking change: the browser-based interface is no
longer included or supported.

If running from source:
```bash
uv run wherewolf
```

To run the Spark integration tier locally after installing the extra and Java:

```bash
uv run pytest -m spark
```

1. Use the **Dataset Catalog** in the desktop shell to browse and add files via native dialogs or drag-and-drop.
2. Each file is assigned a table alias (e.g., `users`, `orders`).
3. Write SQL in the QScintilla editor with SQL IntelliSense (`Ctrl+Space` for completion, table/CTE alias resolution, qualified column completion, function call tips).
4. Click **Run** or press `Ctrl+Return` to execute queries asynchronously using DuckDB.
5. Click **Cancel** or press `Ctrl+.` to cancel active query execution.
6. Execution uses request-scoped isolated DuckDB connections, limit+1 truncation detection, and automatic query history persistence in `~/.wherewolf/history.json`.
7. In the desktop shell, activate a History entry to restore its SQL without executing it. Available
   historical dataset files are restored; unavailable paths are reported in the status bar.
8. Use **View → Reset Layout** to restore the default dock arrangement, or **File → Clear History**
   to empty the persisted history safely.
9. Click **Format SQL** (`Ctrl+Shift+F`) to normalize syntax.

### Manual release checks

Before a release, a human must verify the native window starts without a browser or local web
server, the platform multi-file dialog and clipboard behavior, responsiveness during a running
query, and the workflow on supported Windows, macOS, and Linux desktops. Spark full export is
not implemented and is not claimed by the DuckDB export path.



## Development

Run tests:
```bash
uv run pytest
```

To run an on-demand regression check for native Qt/coverage crashes across multiple test runs:
```bash
./scripts/check_flake.sh [runs]
```

There is also a manual GitHub Actions probe workflow (`.github/workflows/flake-probe.yml`) that dispatches
parallel Python 3.14 test runs with the same Qt/coverage configuration as CI (gated to probe configuration pushes or manual `workflow_dispatch`).

Use it to measure CI-only flake rates without affecting normal branch push/pull_request budgets.

Lint/Format:
```bash
ruff check . --fix
ruff format .
```

## Dependencies
- `PyQt6`
- `PyQt6-QScintilla`
- `duckdb`
- `sqlglot`
- `pyarrow`
- `polars`
- `fastexcel`
- `xlsxwriter`

Optional:

- `pyspark` via `wherewolf[spark]` (requires Java)

## License

Wherewolf is transitioning to `GPL-3.0-only` for future releases.
Releases through `0.5.2` remain available under `MIT`.
The original MIT text is retained in `LICENSES/MIT-pre-0.6.txt` and those grants remain valid.

## Contributing

Contributions are accepted under `GPL-3.0-only`.
