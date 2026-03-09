# Plan: Export Formats

## Problem Definition
Allow users to download full query results in multiple formats (CSV, Excel, Parquet).

## Architecture Overview
-   **Exporter:** A static or utility class to convert Pandas DataFrames to bytes.
-   **Supported Formats:** CSV, XLSX (Excel), Parquet.

## Public Interfaces
-   `Exporter.to_csv(df: pd.DataFrame) -> bytes`
-   `Exporter.to_excel(df: pd.DataFrame) -> bytes`
-   `Exporter.to_parquet(df: pd.DataFrame) -> bytes`

## Implementation Strategy
-   **CSV:** `df.to_csv(index=False).encode('utf-8')`.
-   **Excel:** Use `io.BytesIO()` and `df.to_excel(writer, index=False, engine='openpyxl')`.
-   **Parquet:** Use `io.BytesIO()` and `df.to_parquet(buffer, index=False)`.

## Testing Strategy (RED)
-   Create `tests/test_export.py`.
-   Verify byte output for each format.
-   Verify Excel output can be read back by Pandas.
