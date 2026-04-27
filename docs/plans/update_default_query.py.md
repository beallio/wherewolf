# Plan: Update Default Query on First Dataset Load

## Problem Definition
When `wherewolf` starts, the default query in the SQL editor is `SELECT * FROM dataset LIMIT 10`. 
When a user loads their first dataset, the query remains unchanged. 
The goal is to automatically update the query to `SELECT * FROM {alias} LIMIT 10` when the first dataset is added to the catalog, providing a better "out-of-the-box" experience.

## Architecture Overview
The change is isolated to the UI layer in `src/wherewolf/app.py`. 
The sidebar handles dataset catalog management. 
We will hook into the logic that executes after a file is selected via the `FileBrowser`.

## Implementation Steps

1.  **Modify `src/wherewolf/app.py`**:
    - Locate the block handling `selected_path` from `FileBrowser.render_explorer()` (approx. line 225).
    - Determine if the catalog is empty before adding the new dataset.
    - If it is the first dataset, update `st.session_state.selected_query`.

```python
        if selected_path:
            # Check if this is the first dataset being added
            is_first_dataset = not bool(st.session_state.catalog)

            # Determine alias and add
            alias = get_default_alias(selected_path)
            st.session_state.catalog[alias] = selected_path
            st.session_state.schema_focus = alias
            
            # Auto-update the default query for the first dataset
            if is_first_dataset:
                st.session_state.selected_query = f"SELECT * FROM {alias} LIMIT 10"

            st.success(f"Added `{alias}` to catalog.")
            st.rerun()
```

2.  **Verify existing defaults**:
    - Ensure `st.session_state.selected_query` is still initialized to `SELECT * FROM dataset LIMIT 10` at startup (line 103) as per current behavior.

## Testing Strategy
- **Manual Verification**:
    1. Start the app.
    2. Observe the default query: `SELECT * FROM dataset LIMIT 10`.
    3. Load a CSV file (e.g., `data.csv`).
    4. Observe the query updates to: `SELECT * FROM data LIMIT 10`.
    5. Load a second file (e.g., `other.parquet`).
    6. Observe the query DOES NOT change (it should stay as whatever it was, likely `SELECT * FROM data LIMIT 10` or user's edits).
- **Automated Testing**:
    - I will attempt to add a test case to `tests/test_app.py` that sets `pending_path` or similar to trigger loading, but since `render_explorer` is interactive, a unit test for the sidebar logic specifically might require more extensive mocking than currently available. 
    - However, I can add a test that verifies the *initial* state and then manually verify the transition logic.
