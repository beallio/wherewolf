# Plan: UI Layout Refinement - Export Section

## Problem Definition
The "Export Format" dropdown is currently located in the sidebar, while the "Download" button is in the main results section. This separation is counter-intuitive for users who expect export settings to be co-located with the export action.

## Architecture Overview
-   **UI Refactoring**: Move the `export_format` widget from the sidebar block to the results display block in `app.py`.
-   **Layout**: Use `st.columns` to place the format selector and the download button side-by-side.

## Implementation Steps
1.  Remove the `export_format` selectbox from the sidebar section in `src/wherewolf/app.py`.
2.  Locate the "Export Results" section in the results display logic.
3.  Implement a two-column layout (`st.columns([0.2, 0.8])`).
4.  Place the `export_format` selectbox (with `label_visibility="collapsed"`) in the first column.
5.  Place the `st.download_button` in the second column.

## Verification & Testing
-   **Manual Verification**: Run the app and ensure the dropdown and button appear side-by-side in the results section after a successful query.
-   **Regression Testing**: Ensure the export functionality still works correctly for all formats (CSV, Excel, Parquet).
