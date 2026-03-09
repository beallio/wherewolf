# Plan: File Browsing

## Problem Definition
Manual entry of filesystem paths is error-prone. Provide a native "Browse" button to select data files or folders.

## Architecture Overview
-   **UI:** Add a "Browse" button next to the "Dataset Path" input in the sidebar.
-   **Logic:** Use `tkinter.filedialog.askopenfilename` to open a native file picker.
-   **State Management:** Update `st.session_state.dataset_path` when a file is selected.

## Technical Decisions
-   **Native Picker:** Since this is a local SQL workbench, a native file dialog is the most "production-grade" and intuitive way to select files.
-   **No UI Blocking:** `tkinter` must be used with care in a Streamlit app to avoid blocking the server loop or causing issues with remote displays (though here it's local).

## Public Interfaces
-   `FileBrowser.open_picker() -> str`

## Implementation Strategy
1.  Add `tkinter` imports in `src/wherewolf/app.py`.
2.  Create a "Browse" button in the sidebar.
3.  On click, trigger the file picker and update the session state.

## Testing Strategy (RED)
-   Streamlit UI and `tkinter` interactions are hard to automate in this environment.
-   I'll add a test case in `tests/test_app.py` or a new file to verify that the session state for `dataset_path` is correctly handled.
-   Manual verification of the picker.
