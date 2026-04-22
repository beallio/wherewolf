# Plan: Multiple Datasets Support (Revised)

## Problem Definition
Currently, Wherewolf only supports querying a single dataset at a time, registered under the reserved alias `dataset`. This prevents users from performing JOINs, unions, or subqueries involving multiple files.

## Architecture Overview
The system will shift to a **Dataset Catalog** model:
1.  **Catalog Management**: `st.session_state.catalog` will maintain a `Dict[str, str]` mapping aliases to filesystem paths.
2.  **Engine Registration**: The `execute` method will iterate through the entire catalog and register every dataset as a temporary view in the active engine's context before running the query.
3.  **UI Updates**: 
    -   Sidebar will feature a "Dataset Catalog" list.
    -   A "Metadata Focus" selector will allow users to choose which dataset's schema is shown in the HUD.
4.  **No Cross-Engine Joins**: All JOINs occur within the context of a single active engine (DuckDB or Spark).

## Core Data Structures
-   **Catalog**: `Dict[str, str]` (e.g., `{"orders": "/data/orders.csv", "users": "/data/users.parquet"}`).
-   **HistoryEntry**: Updated to store the `catalog` dictionary alongside the query.

## Technical Decisions
-   **Alias Strategy**: 
    1. Default: `Path(path).stem` (e.g., `sales`).
    2. Collision Fallback: `Path(path).name.replace('.', '_')` (e.g., `sales_csv`).
    3. Final Fallback: Overwrite with UI warning.
-   **Alias Validation**: Strictly enforce `^[a-zA-Z_][a-zA-Z0-9_]*$` and block SQL reserved keywords.
-   **Persistence**: The catalog is **transient** (session-only). It is not saved to disk, though it is captured in the execution history.

## Implementation Strategy

### Phase 1: Engine Refactoring
-   Update `DuckDBEngine` and `SparkEngine` to support a `catalog: Dict[str, str]` in their `execute` methods.
-   Implement idempotent registration (only re-register if path/alias pair has changed).
-   Update `get_schema` to be alias-agnostic.

### Phase 2: UI - Catalog Management
-   Add "Add to Catalog" flow after file selection.
-   Implement the filename-prioritized aliasing logic.
-   Add a list of active datasets to the sidebar with "Remove" actions.

### Phase 3: Schema HUD & History
-   Refactor Schema HUD to allow selecting which cataloged dataset to inspect.
-   Update `HistoryManager` to handle legacy history (wrap single path into a `{"dataset": path}` catalog) and save new multi-dataset history.

## Robustness & Compatibility
-   **Legacy Support**: `HistoryManager` will transparently convert legacy entries.
-   **Sanitization**: Centralized utility to validate and clean aliases.
-   **Error Handling**: Explicitly report which alias failed to load if a file is missing.

## Testing Strategy
1.  **Engine Tests**: Verify JOINs between CSV and Parquet in both DuckDB and Spark.
2.  **Alias Tests**: Verify the filename -> filename_ext fallback logic.
3.  **History Tests**: Verify restoration of a 3-table catalog from a history entry.

## Definition of Done
- [ ] Users can load multiple files with distinct aliases.
- [ ] JOIN queries work correctly in both engines.
- [ ] Catalog is manageable via the UI.
- [ ] Legacy history is preserved and accessible.
