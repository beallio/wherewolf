# Plan: Streamlit UI

## Problem Definition
Provide a user-friendly web interface to interact with the execution engines, view results, and manage history.

## Architecture Overview
-   **Sidebar:** Dataset path input, Engine selection, Preview limit, Export format, History list.
-   **Main Area:** SQL Editor, Run/Cancel buttons, Result metrics, Preview Table, Translated SQL block.
-   **State Management:** Use `st.session_state` for current query, results, and cancellation flags.

## Implementation Strategy
-   **Threaded execution:** Run `engine.execute` in a separate thread to allow the UI to show a "Running..." state and a "Cancel" button.
-   **Cancellation:** Use a `threading.Event` and call `engine.interrupt()`.
-   **SQL Translation:** Trigger `Translator.translate` on query change or engine change.
-   **History integration:** Load history on startup and update it after successful queries.
-   **Error Handling:** Use `st.error` with a detailed expander for tracebacks.

## UI Layout
1.  `st.sidebar`:
    -   `st.text_input` for dataset path.
    -   `st.selectbox` for Engine (DuckDB, Spark).
    -   `st.slider` for preview limit (10-1000).
    -   `st.selectbox` for Export format.
    -   `st.header("History")` + `st.button`s or a selectbox for past queries.
2.  `st.main`:
    -   `st.code_editor` (or `st.text_area` for simplicity).
    -   Columns for "Run" and "Cancel".
    -   `st.metric` for rows and time.
    -   `st.dataframe` for results.
    -   `st.expander("Translated SQL")` showing the transpiled query.

## Testing Strategy
-   Streamlit is hard to unit test conventionally.
-   I'll use `streamlit.testing.v1.AppTest` if possible, or focus on verifying that the `app.py` can be imported and runs without immediate syntax errors.
-   Manual verification of the UI flow.
