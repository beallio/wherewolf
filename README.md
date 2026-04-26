# Wherewolf

<img src="https://raw.githubusercontent.com/beallio/wherewolf/main/src/wherewolf/assets/img/wherewolf_banner.png?cacheBuster=7" width="100%">

[![CI](https://github.com/beallio/wherewolf/actions/workflows/ci.yml/badge.svg?cacheBuster=7)](https://github.com/beallio/wherewolf/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/wherewolf.svg?cacheBuster=7)](https://pypi.org/project/wherewolf/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?cacheBuster=7)](https://opensource.org/licenses/MIT)

A production-grade, local SQL workbench for querying files (CSV, Parquet, JSON) using DuckDB or Spark.

## Features
- **Multi-Engine Support:** Execute SQL via DuckDB (local) or Spark (local[*]). Native support for CSV, Parquet, JSON, and Excel (`.xlsx`, `.xls`).
- **📁 Dataset Catalog:** Load multiple files simultaneously and assign custom SQL aliases for complex analysis.
- **🔗 Multi-Table Queries:** Perform JOINs, unions, and subqueries across different file formats in a single session.
- **📊 Schema & Metadata HUD:** Instant visibility of column names and data types for any dataset in your catalog.
- **SQL Translation:** Real-time translation between DuckDB and SparkSQL dialects using SQLGlot.
- **Modern UI:** Distraction-free interface with a hidden toolbar, reduced whitespace, and clear visual hierarchy.
- **Safe Preview:** Scrollable results limited to 1000 rows.
- **Query History:** Persists past queries in `~/.wherewolf/history.json`.
- **Export:** Download query results as CSV, Excel, or Parquet.
- **Execution Metrics:** Tracks row count and execution time.

![Wherewolf Screenshot](https://raw.githubusercontent.com/beallio/wherewolf/main/src/wherewolf/assets/img/screenshot.png?cacheBuster=7)

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

If running from source:
```bash
uv run streamlit run src/wherewolf/app.py
```

1. Use the **Manage Dataset Catalog** section in the sidebar to browse and add files.
2. Each file is assigned an alias (e.g., `users`, `orders`).
3. Write your SQL query using these aliases in the editor.
4. Click **Run** to execute.
5. View results, execution metrics, or switch the **Metadata Focus** to inspect other schemas.
6. Export or view the translated SQL if needed.

## Development

Run tests:
```bash
uv run pytest
```

Lint/Format:
```bash
ruff check . --fix
ruff format .
```

For information on how to release new versions, see [RELEASING.md](docs/RELEASING.md).

## Dependencies
- `streamlit`
- `duckdb`
- `pyspark`
- `ibis-framework`
- `sqlglot`
- `pandas`
- `pyarrow`
- `openpyxl`
