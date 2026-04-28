# Plan: Enhance File Browser with Sorting and Icons

## Objective
Improve the file browser UI by sorting directories to the top and adding a folder icon to directory entries in the dropdown.

## Key Files & Context
- `src/wherewolf/ui/file_browser.py`: Main implementation of the file explorer.
- `tests/test_file_browser_filtering.py`: Recently added tests for filtering logic.

## Proposed Solution
1. **Sorting Logic**: 
   - Modify `render_explorer` to group directories and files separately.
   - Ensure directories appear first in the `filtered_items` list.
2. **Visual Enhancement (Icons)**:
   - Implement a `format_item` helper function within `render_explorer`.
   - Use icons ONLY for directories:
     - Directory: 📁
     - Parent Directory (..): ⤴️
     - Files: No icon (raw filename)
   - Pass `format_item` to `st.selectbox`'s `format_func` parameter.
3. **Verification**:
   - Update tests to verify sorting order.
   - Ensure path resolution remains correct (underlying selectbox values should remain raw strings).

## Implementation Steps
### 1. Research & Verification
- [x] Confirm `st.selectbox(format_func=...)` behavior (it only affects display, not value).

### 2. TDD (Red)
- [ ] Update `tests/test_file_browser_filtering.py` to assert that directories appear before files in the session state `files_key`.

### 3. Implementation (Green)
- [ ] Update `src/wherewolf/ui/file_browser.py`:
  - Implement sorting logic in `render_explorer`.
  - Implement `format_item` and pass it to `st.selectbox`.

### 4. Refactor
- [ ] Ensure the placeholder and ".." are handled correctly in formatting.
- [ ] Run `ruff` and `ty` checks.

### 5. Validation
- [ ] Run `pytest`.
- [ ] Manually verify icons and sorting in Streamlit UI.

## Verification & Testing
- Updated `tests/test_file_browser_filtering.py` will cover:
  - Directories sorted before files.
  - Correct identification of directories vs. files.
- Manual check for:
  - Visual icons in the dropdown for folders only.
  - ".." having a unique icon.
