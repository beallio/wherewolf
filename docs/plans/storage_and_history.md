# Plan: Storage and History

## Problem Definition
Persist query execution history across sessions to allow users to reuse past queries.

## Architecture Overview
-   **HistoryManager:** Class to handle JSON file operations for history.
-   **Location:** Default to `~/.wherewolf/history.json`.
-   **Structure:** A list of dictionaries.

## Core Data Structures
-   **HistoryEntry:**
    ```python
    {
        "timestamp": "ISO8601 string",
        "engine": "duckdb|spark",
        "query": "SELECT ...",
        "path": "/path/to/data"
    }
    ```

## Public Interfaces
-   `HistoryManager.add_entry(engine: str, query: str, path: str)`
-   `HistoryManager.get_all() -> List[Dict]`
-   `HistoryManager.clear()`

## Implementation Strategy
-   Ensure the directory `~/.wherewolf` exists.
-   Use `json` module for atomic-like writes (write to temp file, then rename).
-   Limit history size to 100 entries (optional but good for performance).

## Testing Strategy (RED)
-   Create `tests/test_storage.py`.
-   Mock the home directory or provide a test-specific path.
-   Test `add_entry` and `get_all`.
-   Verify JSON format.
