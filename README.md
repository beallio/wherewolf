# Wherewolf

<img src="https://raw.githubusercontent.com/beallio/wherewolf/main/src/wherewolf/assets/img/wherewolf_banner.png?cacheBuster=13" width="100%">

[![CI](https://github.com/beallio/wherewolf/actions/workflows/ci.yml/badge.svg?cacheBuster=13)](https://github.com/beallio/wherewolf/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/wherewolf.svg?cacheBuster=13)](https://pypi.org/project/wherewolf/)
[![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-blue.svg?cacheBuster=13)](https://www.gnu.org/licenses/gpl-3.0.html)

A production-grade, local SQL workbench for querying files (CSV, Parquet, JSON) using DuckDB or Spark.

## Features
- **Multi-Engine Support:** Execute SQL via DuckDB (local) or Spark (local[*]). Native support for CSV, Parquet, JSON, and Excel (`.xlsx`, `.xls`).
- **📁 Dataset Catalog:** Improved catalog in the desktop shell with native dialogs and drag-and-drop file intake.
- **🧰 Desktop SQL Editor:** QScintilla-based editor with line numbers, brace matching, SQL formatting, function call tips, and intelligent SQL completion (`Ctrl+Space` shortcut and configurable auto-trigger threshold).
- **🔗 Multi-Table Queries:** Perform JOINs, unions, and subqueries across different file formats in a single session.
- **📊 Schema & Metadata HUD:** Instant visibility of column names and data types for any dataset in your catalog.
- **SQL Translation:** Real-time translation between DuckDB and SparkSQL dialects using SQLGlot.
- **Modern UI:** Distraction-free interface with a hidden toolbar, reduced whitespace, and clear visual hierarchy.
- **Safe Preview:** Scrollable results limited to 1000 rows.
- **Query History:** Persists past queries in `~/.wherewolf/history.json`.
- **Export:** Download query results as CSV, Excel, or Parquet. DataFrame handling and exports are Polars-based. When the preview is truncated, use **Prepare full export** to re-run the query without a row limit and download the entire result set.
- **Execution Metrics:** Tracks row count and execution time.

![Wherewolf Screenshot](https://raw.githubusercontent.com/beallio/wherewolf/main/src/wherewolf/assets/img/screenshot.png?cacheBuster=13)

## Installation

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

### From PyPI (Recommended)
```bash
uv tool install wherewolf
wherewolf
```

### From Source
```bash
git clone https://github.com/beallio/wherewolf.git
cd wherewolf
uv sync
```

## Usage
The default `wherewolf` command continues to start the Streamlit UI.
The temporary desktop shell is launched with `wherewolf-desktop` and is a work-in-progress;
it will replace the Streamlit launcher at the final migration cutover.
Query execution is not yet implemented in this desktop stage.

If running from source:
```bash
uv run streamlit run src/wherewolf/app.py
wherewolf-desktop
```

1. Use the **Dataset Catalog** in the desktop shell to browse and add files via native dialog or drag-and-drop.
2. Each file is assigned an alias (e.g., `users`, `orders`).
3. Write SQL in the QScintilla editor with SQL IntelliSense (`Ctrl+Space` for manual autocompletion, automatic suggestion after typing 2 characters, table/CTE alias resolution, qualified column completion, function call tips).
4. Click **Format SQL** to normalize syntax.
5. View schema metadata from the catalog.
6. Query execution is coming in a later phase.


## Development

Run tests:
```bash
uv run pytest
```

To run an on-demand regression check for native Qt/coverage crashes across multiple test runs:
```bash
./scripts/check_flake.sh [runs]
```

Lint/Format:
```bash
ruff check . --fix
ruff format .
```

## Dependencies
- `streamlit`
- `duckdb`
- `pyspark`
- `sqlglot`
- `pyarrow`
- `polars`
- `fastexcel`
- `xlsxwriter`

## License

Wherewolf is transitioning to `GPL-3.0-only` for future releases.
Releases through `0.5.2` remain available under `MIT`.
The original MIT text is retained in `LICENSES/MIT-pre-0.6.txt` and those grants remain valid.

## Contributing

Contributions are accepted under `GPL-3.0-only`.
