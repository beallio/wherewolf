import streamlit as st
from wherewolf.execution import DuckDBEngine, SparkEngine, QueryResult
from wherewolf.translation import Translator
from wherewolf.storage import HistoryManager
from wherewolf.export import Exporter
from wherewolf.ui import FileBrowser
from streamlit_ace import st_ace

# --- Configuration ---
st.set_page_config(
    page_title="Wherewolf SQL Workbench",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Hide Streamlit options (hamburger menu and footer)
hide_st_style = """
            <style>
            /* Hide the Streamlit main menu (hamburger) */
            #MainMenu {visibility: hidden;}
            /* Hide the "Made with Streamlit" footer */
            footer {visibility: hidden;}
            /* 
               We do NOT hide 'header' entirely because it contains 
               the sidebar toggle button when collapsed.
            */
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- Initialize Session State ---
if "path_input" not in st.session_state:
    st.session_state.path_input = ""
if "query_result" not in st.session_state:
    st.session_state.query_result = None
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "history" not in st.session_state:
    st.session_state.history = []
if "selected_query" not in st.session_state:
    st.session_state.selected_query = "SELECT * FROM dataset LIMIT 10"

# --- Early State Update Pattern ---
# This avoids StreamlitAPIException by updating state BEFORE widgets are instantiated.
if "pending_path" in st.session_state:
    st.session_state.path_input = st.session_state.pending_path
    del st.session_state.pending_path

if "pending_query" in st.session_state:
    st.session_state.selected_query = st.session_state.pending_query
    del st.session_state.pending_query

# --- Instances ---
history_manager = HistoryManager()
translator = Translator()

# --- Sidebar ---
with st.sidebar:
    st.title("🐺 Wherewolf")

    # 1. BROWSE LOGIC
    # The browser is now the primary path selection tool.
    with st.expander("📁 Browse Local Files", expanded=True):
        show_hidden = st.checkbox("Show Hidden Files", value=False)
        selected_path = FileBrowser.render_explorer(show_hidden=show_hidden)
        if selected_path:
            # Set PENDING path and rerun
            st.session_state.pending_path = selected_path
            st.rerun()

    # Display the active path clearly in the sidebar
    if st.session_state.path_input:
        st.info(f"📄 Active: `{st.session_state.path_input}`")
    else:
        st.warning("⚠️ No dataset loaded.")

    engine_name = st.selectbox("Execution Engine", ["DuckDB", "Spark"])

    preview_limit = st.slider("Preview Size", 10, 1000, 100)
    export_format = st.selectbox("Export Format", ["CSV", "Excel", "Parquet"])

    st.divider()
    st.subheader("Query History")
    history = history_manager.get_all()
    if history:
        history_labels = [f"{h['timestamp'][:16]} - {h['query'][:30]}..." for h in history]
        selected_history = st.selectbox("Select from History", ["Select..."] + history_labels)
        if selected_history != "Select...":
            idx = history_labels.index(selected_history)
            # Use PENDING state to avoid instantiation errors
            st.session_state.pending_query = history[idx]["query"]
            st.session_state.pending_path = history[idx]["path"]
            st.rerun()
    else:
        st.write("No history yet.")

    if st.button("Clear History"):
        history_manager.clear()
        st.rerun()

    st.divider()
    st.subheader("Editor Settings")
    themes = sorted(
        [
            "tomorrow_night_eighties",
            "monokai",
            "twilight",
            "ambiance",
            "chaos",
            "clouds_midnight",
            "dracula",
            "gob",
            "solarized_dark",
            "terminal",
            "vibrant_ink",
            "chrome",
            "clouds",
            "crimson_editor",
            "dawn",
            "dreamweaver",
            "eclipse",
            "github",
            "solarized_light",
            "textmate",
            "tomorrow",
            "xcode",
        ]
    )
    ace_theme = st.selectbox(
        "Editor Theme",
        themes,
        index=themes.index("dracula"),
    )

# --- Main Area ---
st.header("SQL Editor")

# Use st_ace for syntax highlighting
query_text = st_ace(
    value=st.session_state.selected_query,
    language="sql",
    theme=ace_theme,
    height=300,
    key="sql_editor",
    auto_update=True,
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

    if engine_name == "DuckDB":
        engine = DuckDBEngine()
    else:
        engine = SparkEngine()

    with st.spinner(f"Running query on {engine_name}..."):
        result = engine.execute(query_text, st.session_state.path_input, limit=preview_limit)
        st.session_state.query_result = result
        st.session_state.selected_query = query_text

        if result.success:
            history_manager.add_entry(engine_name.lower(), query_text, st.session_state.path_input)

    st.session_state.is_running = False
    st.rerun()

# --- Results Display ---
if st.session_state.query_result:
    result: QueryResult = st.session_state.query_result

    if result.success:
        target_dialect = "spark" if engine_name == "DuckDB" else "duckdb"
        try:
            translated_sql = translator.translate(
                query_text, from_dialect=engine_name.lower(), to_dialect=target_dialect
            )
            with st.expander(f"✨ Translated SQL ({target_dialect.capitalize()})", expanded=True):
                st.code(translated_sql, language="sql")
        except Exception as e:
            st.warning(f"Translation failed: {str(e)}")

        m1, m2 = st.columns(2)
        m1.metric("Rows Returned", f"{result.row_count:,}")
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

        # Derive original filename for the export
        import os

        orig_filename = os.path.basename(st.session_state.path_input)
        # Strip extension from original if present
        base_name = os.path.splitext(orig_filename)[0] or "wherewolf"
        download_name = f"{base_name}_export{ext}"

        st.download_button(label=export_label, data=data, file_name=download_name, mime=mime)

    else:
        st.error("Query Failed")
        with st.expander("Show Details"):
            st.text(result.error_message)

elif not st.session_state.path_input:
    st.info("👈 Please provide a dataset path in the sidebar to begin.")
