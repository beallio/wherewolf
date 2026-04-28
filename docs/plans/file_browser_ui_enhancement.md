# Plan: Enhance File Browser UI and UX

## Objective
Improve the file browser UI by sorting directories to the top, adding folder icons, and using a native selectbox placeholder instead of a placeholder option in the list.

## Key Files & Context
- `src/wherewolf/ui/file_browser.py`: Main implementation of the file explorer.
- `tests/test_file_browser_filtering.py`: Tests for filtering and sorting logic.

## Proposed Solution
1. **Sorting Logic**: Group directories (sorted) first, followed by supported files (sorted).
2. **Visual Enhancement (Icons)**:
   - Use `format_func` in `st.selectbox` to add 📁 for folders and ⤴️ for `..`.
   - Files will have no icons.
3. **UX Improvement (Native Placeholder)**:
   - Remove "Select file/folder..." from the `options` list.
   - Use `index=None` and `placeholder="Select file/folder..."` in `st.selectbox`.
   - Update `_update_dir` to handle `None` selection.
   - Update `render_explorer` to handle `None` return value.

## Implementation Steps
### 1. Research & Verification
- [x] Confirm `st.selectbox(index=None, placeholder=...)` behavior in Streamlit 1.55.0.

### 2. TDD (Red)
- [ ] Update `tests/test_file_browser_filtering.py` to verify "Select file/folder..." is NOT in the session state `files_key`.

### 3. Implementation (Green)
- [ ] Update `src/wherewolf/ui/file_browser.py`:
  - Remove placeholder string from `options`.
  - Update `st.selectbox` parameters.
  - Update `_update_dir` and `render_explorer` logic.

### 4. Refactor
- [ ] Run `ruff` and `ty` checks.

### 5. Validation
- [ ] Run `pytest`.
- [ ] Manually verify the dropdown is clean and shows the placeholder prompt correctly.
