import streamlit as st
from wherewolf.execution import DuckDBEngine, SparkEngine, QueryResult
from wherewolf.translation import Translator
from wherewolf.storage import HistoryManager
from wherewolf.export import Exporter
from wherewolf.ui import FileBrowser

# --- Configuration ---
st.set_page_config(page_title="Wherewolf SQL Workbench", layout="wide")

# --- Initialize Session State ---
if "path_input" not in st.session_state:
    st.session_state.path_input = ""
if "query_result" not in st.session_state:
    st.session_state.query_result = None
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "history" not in st.session_state:
    st.session_state.history = []

# --- Instances ---
history_manager = HistoryManager()
translator = Translator()

# --- Sidebar ---
with st.sidebar:
    st.title("🐺 Wherewolf")

    col_path, col_browse = st.columns([0.7, 0.3])
    with col_path:
        st.text_input(
            "Dataset Path (local)",
            placeholder="/path/to/data.parquet",
            key="path_input",
        )
    with col_browse:
        st.write("")  # alignment
        st.write("")
        if st.button("📁 Browse"):
            selected_path = FileBrowser.select_file()
            if selected_path:
                st.session_state.path_input = selected_path
                st.rerun()

    engine_name = st.selectbox("Execution Engine", ["DuckDB", "Spark"])
    preview_limit = st.slider("Preview Size", 10, 1000, 100)
    export_format = st.selectbox("Export Format", ["CSV", "Excel", "Parquet"])

    st.divider()
    st.subheader("Query History")
    history = history_manager.get_all()
    if history:
        # History selection in a selectbox
        history_labels = [f"{h['timestamp'][:16]} - {h['query'][:30]}..." for h in history]
        selected_history = st.selectbox("Select from History", ["Select..."] + history_labels)
        if selected_history != "Select...":
            idx = history_labels.index(selected_history)
            st.session_state.selected_query = history[idx]["query"]
            st.session_state.path_input = history[idx]["path"]
            # Trigger rerun to update the editor
            st.rerun()
    else:
        st.write("No history yet.")

    if st.button("Clear History"):
        history_manager.clear()
        st.rerun()

# --- Main Area ---
st.header("SQL Editor")

# Use st.session_state.selected_query if it exists
initial_query = getattr(st.session_state, "selected_query", "SELECT * FROM dataset LIMIT 10")
query_text = st.text_area(
    "SQL Query", value=initial_query, height=200, help="Use 'dataset' as the table name."
)

col1, col2 = st.columns([0.1, 0.9])
with col1:
    run_button = st.button("🚀 Run", type="primary", disabled=st.session_state.is_running)
with col2:
    cancel_button = st.button("🛑 Cancel", disabled=not st.session_state.is_running)

# --- Execution Logic ---
if run_button and st.session_state.path_input:
    st.session_state.is_running = True
    st.session_state.query_result = None

    # Engine Selection
    if engine_name == "DuckDB":
        engine = DuckDBEngine()
    else:
        engine = SparkEngine()

    with st.spinner(f"Running query on {engine_name}..."):
        result = engine.execute(query_text, st.session_state.path_input, limit=preview_limit)
        st.session_state.query_result = result

        if result.success:
            history_manager.add_entry(engine_name.lower(), query_text, st.session_state.path_input)

    st.session_state.is_running = False
    st.rerun()

# --- Results Display ---
if st.session_state.query_result:
    result: QueryResult = st.session_state.query_result

    if result.success:
        m1, m2 = st.columns(2)
        m1.metric("Rows Returned", result.row_count)
        m2.metric("Execution Time", f"{result.execution_time:.4f}s")

        st.subheader("Preview")
        st.dataframe(result.df, width="stretch")

        # --- Export Section ---
        st.divider()
        st.subheader("Export Results")

        export_label = f"Download as {export_format}"
        if export_format == "CSV":
            data = Exporter.to_csv(result.df)
            mime = "text/csv"
            ext = ".csv"
        elif export_format == "Excel":
            data = Exporter.to_excel(result.df)
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ext = ".xlsx"
        else:
            data = Exporter.to_parquet(result.df)
            mime = "application/octet-stream"
            ext = ".parquet"

        st.download_button(
            label=export_label, data=data, file_name=f"wherewolf_export{ext}", mime=mime
        )

        # --- Translation Section ---
        with st.expander("Translated SQL"):
            target_dialect = "spark" if engine_name == "DuckDB" else "duckdb"
            try:
                translated_sql = translator.translate(
                    query_text, from_dialect=engine_name.lower(), to_dialect=target_dialect
                )
                st.code(translated_sql, language="sql")
            except Exception as e:
                st.warning(f"Translation failed: {str(e)}")

    else:
        st.error("Query Failed")
        with st.expander("Show Details"):
            st.text(result.error_message)

elif not st.session_state.path_input:
    st.info("👈 Please provide a dataset path in the sidebar to begin.")
