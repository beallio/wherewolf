# Plan: Excel File Support

## Problem Definition
Users want to query Excel files (`.xlsx`, `.xls`) directly within Wherewolf, similar to how they query CSV, Parquet, and JSON files.

## Architecture Overview
- **DuckDBEngine:** Utilize the DuckDB `excel` extension. This requires running `INSTALL excel; LOAD excel;` and using `excel_scan(?)`.
- **SparkEngine:** Since native Spark Excel support requires external JARs (e.g., `spark-excel`), and Wherewolf runs in a local environment, we will use `pandas` to read the Excel file and then convert it to a Spark DataFrame as a fallback for this engine.
- **FileBrowser:** Update the allowed extensions to include `.xlsx` and `.xls`.

## Core Data Structures
No changes to `QueryResult`.

## Public Interfaces
- No API changes.
- UI: `FileBrowser.render_explorer` will now permit loading of Excel files.

## Dependency Requirements
- `openpyxl` (already present for export)
- `duckdb` (already present, requires extension install at runtime)
- `pandas` (already present)

## Testing Strategy
- Create `tests/test_excel_support.py`.
- Verify DuckDB can read a sample `.xlsx`.
- Verify Spark can read a sample `.xlsx`.
- Verify UI logic allows the extensions.

## Task Decomposition
- **Task 1: DuckDB Excel Logic**
  - Implement extension loading and `excel_scan` in `src/wherewolf/execution/duckdb_engine.py`.
- **Task 2: Spark Excel Logic**
  - Implement pandas-based bridge for Excel in `src/wherewolf/execution/spark_engine.py`.
- **Task 3: UI Extension Update**
  - Update `src/wherewolf/ui/file_browser.py` to include `.xlsx` and `.xls`.
- **Task 4: Verification**
  - Add and run tests.
