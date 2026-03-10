# Plan: File Browsing V2 (st-file-browser)

## Problem Definition
Replace the custom Streamlit file explorer with a more robust and professional third-party component (`st-file-browser`).

## Architecture Overview
-   **Component:** Use `st_file_browser` from `st_file_browser` package.
-   **Integration:** Update `src/wherewolf/ui/file_browser.py` to wrap the new component.
-   **Input/Output:** The component returns a dictionary or None. We need to extract the path of the selected file.

## Implementation Strategy
1.  Import `st_file_browser`.
2.  Update `FileBrowser.render_explorer` to call `st_file_browser(path, key='...')`.
3.  Handle the return value to detect when a file is selected.
4.  Ensure it integrates with the "Early Update" pattern in `app.py`.

## Testing Strategy (RED)
-   Create `tests/test_file_browser_v2.py`.
-   Verify that the `FileBrowser` class interface remains consistent so `app.py` doesn't break.
-   Since it's a third-party component with JS, automated UI testing is limited; focus on structural integrity.
