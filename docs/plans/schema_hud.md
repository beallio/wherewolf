# Plan: Schema & Metadata HUD

## Problem Definition
Users currently have no visual way to see the column names and data types of a loaded dataset without running a manual query like `SELECT * FROM dataset LIMIT 1`. This leads to friction when writing queries, especially for datasets with many or complex column names.

## Architecture Overview
The Schema HUD will be integrated into the existing engine-based architecture:
1.  **Engines (`DuckDBEngine`, `SparkEngine`)**: Will be extended with a `get_schema(path: str)` method that returns a summary of the dataset's structure.
2.  **UI (`app.py`)**: Will trigger a schema fetch when a new file is loaded and display the results in a "Schema Preview" section in the sidebar.
3.  **State Management**: The schema will be cached in `st.session_state` to avoid redundant engine calls.

## Core Data Structures
The schema will be represented as a `pandas.DataFrame` with the following columns:
-   `Column`: The name of the field.
-   `Type`: The detected data type (e.g., `VARCHAR`, `INTEGER`, `struct`).

## Public Interfaces
-   `DuckDBEngine.get_schema(path: str) -> pd.DataFrame`: Uses `DESCRIBE dataset` or native relation metadata.
-   `SparkEngine.get_schema(path: str) -> pd.DataFrame`: Uses `df.schema` or `DESCRIBE dataset`.

## Dependency Requirements
-   Existing dependencies (`duckdb`, `pyspark`, `pandas`, `streamlit`) are sufficient.

## Implementation Plan

### Phase 1: Engine Enhancements
-   [ ] **Refactor `DuckDBEngine`**:
    -   Extract file-to-view registration logic into a private `_register_view(path)` method.
    -   Implement `get_schema(path)`: registers the view and runs `DESCRIBE dataset`.
-   [ ] **Refactor `SparkEngine`**:
    -   Extract file-to-view registration logic into a private `_register_view(path)` method.
    -   Implement `get_schema(path)`: registers the view and runs `DESCRIBE dataset`.

### Phase 2: UI Integration
-   [ ] **Update `app.py` Session State**:
    -   Initialize `st.session_state.schema = None`.
-   [ ] **Update Path Processing**:
    -   When `pending_path` is detected, trigger `get_schema` using the currently selected engine.
    -   Store the result in `st.session_state.schema`.
-   [ ] **Add Sidebar HUD**:
    -   Add an `st.expander("📊 Schema Preview")` in the sidebar below the "Active Path" info.
    -   Display the schema DataFrame if available.

### Phase 3: Robustness & Polishing
-   [ ] Handle edge cases (e.g., empty files, unsupported formats) gracefully within `get_schema`.
-   [ ] Ensure `get_schema` is non-blocking or fast enough for the UI (metadata-only operations are typically very fast).

## Testing Strategy
-   **Unit Tests**:
    -   `tests/test_duckdb_engine.py`: Add `test_get_schema` verifying column names/types for CSV and Parquet.
    -   `tests/test_spark_engine.py`: Add `test_get_schema` verifying column names/types for CSV and Parquet.
-   **Integration Tests**:
    -   Verify that switching engines refreshes the schema HUD correctly.
    -   Verify that the HUD persists across query executions.

## Git & Workflow
-   **Feature Branch**: Create a new branch `feat/schema-hud`.
-   **Commits**: Use imperative style (e.g., "Add get_schema to DuckDBEngine").
-   **Finalization**: Merge to `main` (if requested) or leave for review.

## Verification
-   [ ] `uv run pytest` passes.
-   [ ] `ruff check . --fix` and `ruff format .` pass.
-   [ ] `ty check .` (or `uv run ty`) passes if applicable.
-   [ ] Manual verification: Load a Parquet file and confirm columns appear in the sidebar.

## Definition of Done
- [ ] Tests pass.
- [ ] Linter/Formatter pass.
- [ ] `ty` check passes.
- [ ] Session log recorded in `docs/agent_conversations/`.
- [ ] README updated if necessary (not needed for this internal UI feature).
