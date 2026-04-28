# Plan: Filter File Browser by Extension

## Objective
Filter the file selection dropdown in the Streamlit UI to only show directories and files with supported extensions (`.csv`, `.parquet`, `.json`, `.xlsx`, `.xls`).

## Key Files & Context
- `src/wherewolf/ui/file_browser.py`: Current implementation of the file browser.
- `src/wherewolf/app.py`: UI entry point that calls the file browser.
- `src/wherewolf/execution/duckdb_engine.py`: Uses file extensions to determine how to load data.
- `src/wherewolf/execution/spark_engine.py`: Also uses file extensions.

## Proposed Solution
1. **Centralize Supported Extensions**: Create `src/wherewolf/constants.py` with `SUPPORTED_EXTENSIONS = {".csv", ".parquet", ".json", ".xlsx", ".xls"}`.
2. **Update Engines**: Refactor `DuckDBEngine` and `SparkEngine` to potentially use these constants (optional but good for consistency).
3. **Update `FileBrowser.render_explorer`**:
   - Add logic to filter items returned by `os.listdir`.
   - Ensure all directories are always shown to allow navigation.
   - Only show files if their lowercased extension is in `SUPPORTED_EXTENSIONS`.
4. **Update `app.py`**: Ensure it works with the updated `FileBrowser`.

## Implementation Steps
### 1. Research & Verification
- [x] Confirm current supported extensions in `file_browser.py` and engines.
- [x] Identify where `os.listdir` is called in `file_browser.py`.

### 2. TDD (Red)
- [ ] Create `tests/test_file_browser_filtering.py`.
- [ ] Write a test that mocks `os.listdir` and verifies that only directories and allowed files are returned in `st.session_state`.

### 3. Implementation (Green)
- [ ] Create `src/wherewolf/constants.py`.
- [ ] Update `src/wherewolf/ui/file_browser.py`:
  - Import `SUPPORTED_EXTENSIONS`.
  - Filter `raw_items` in `render_explorer`.
- [ ] Update `src/wherewolf/execution/duckdb_engine.py` to use `SUPPORTED_EXTENSIONS` (if applicable).
- [ ] Update `src/wherewolf/execution/spark_engine.py` to use `SUPPORTED_EXTENSIONS` (if applicable).

### 4. Refactor
- [ ] Ensure `render_explorer` signature is clean.
- [ ] Run `ruff` and `ty` checks.

### 5. Validation
- [ ] Run `pytest`.
- [ ] Manually verify in Streamlit UI.

## Verification & Testing
- New test file `tests/test_file_browser_filtering.py` will cover:
  - Showing all directories.
  - Showing only files with `.csv`, `.parquet`, `.json`, `.xlsx`, `.xls` extensions.
  - Hiding other files (e.g., `.txt`, `.py`, `.md`).
  - Handling empty directories.
  - Respecting `show_hidden` flag.
