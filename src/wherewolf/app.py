import streamlit as st
import os
from concurrent.futures import ThreadPoolExecutor
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
            /* Hide the Deploy button specifically */
            .stAppDeployButton {display: none;}
            
            /* Darken the sidebar */
            [data-testid="stSidebar"] {
                background-color: #000000;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)


@st.cache_resource
def get_executor():
    return ThreadPoolExecutor(max_workers=4)


executor = get_executor()

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
if "executed_query" not in st.session_state:
    st.session_state.executed_query = ""
if "executed_input_dialect_key" not in st.session_state:
    st.session_state.executed_input_dialect_key = "duckdb"
if "last_engine_name" not in st.session_state:
    st.session_state.last_engine_name = "DuckDB"
if "input_dialect_ui" not in st.session_state:
    st.session_state.input_dialect_ui = "DuckDB"
if "active_engine" not in st.session_state:
    st.session_state.active_engine = None
if "query_future" not in st.session_state:
    st.session_state.query_future = None
if "schema" not in st.session_state:
    st.session_state.schema = None
if "last_schema_path" not in st.session_state:
    st.session_state.last_schema_path = ""
if "last_schema_engine" not in st.session_state:
    st.session_state.last_schema_engine = ""

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
    # Use base64 to embed logo for custom HTML
    import base64
    from pathlib import Path

    logo_path = Path(__file__).parent / "assets/img/wherewolf_logo.png"
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
            <img src="data:image/png;base64,{logo_b64}" width="60">
            <h1 style="margin: 0; white-space: nowrap; font-size: 2.2rem;">Wherewolf</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

    # --- Schema HUD Logic ---
    if st.session_state.path_input:
        # Refresh schema if path or engine changed
        if (
            st.session_state.path_input != st.session_state.last_schema_path
            or engine_name != st.session_state.last_schema_engine
        ):
            try:
                if engine_name == "DuckDB":
                    temp_engine = DuckDBEngine()
                else:
                    temp_engine = SparkEngine()
                st.session_state.schema = temp_engine.get_schema(st.session_state.path_input)
                st.session_state.last_schema_path = st.session_state.path_input
                st.session_state.last_schema_engine = engine_name
            except Exception as e:
                st.session_state.schema = None
                st.sidebar.error(f"Failed to fetch schema: {e}")

        if st.session_state.schema is not None and not st.session_state.schema.empty:
            with st.expander("📊 Schema Preview", expanded=True):
                st.dataframe(
                    st.session_state.schema,
                    hide_index=True,
                    use_container_width=True,
                    height=200,
                )
        elif st.session_state.schema is not None:
            st.caption("No columns detected.")

    # Auto-align input dialect if engine changes
    if st.session_state.last_engine_name != engine_name:
        st.session_state.input_dialect_ui = engine_name
        st.session_state.last_engine_name = engine_name

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
col_h1, col_h2 = st.columns([0.7, 0.3])
with col_h1:
    st.header("SQL Editor")
with col_h2:
    input_dialect_ui = st.selectbox(
        "Input Dialect", options=["DuckDB", "Spark", "Azure SQL"], key="input_dialect_ui"
    )

# --- Autorefresh while running ---
if st.session_state.is_running and "PYTEST_CURRENT_TEST" not in os.environ:
    import time

    time.sleep(0.1)
    st.rerun()

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
    run_button = st.button(
        "🚀 Run",
        type="primary",
        disabled=st.session_state.is_running or not st.session_state.path_input,
    )
with col2:
    cancel_button = st.button("🛑 Cancel", disabled=not st.session_state.is_running)

# --- Execution Logic ---
# Handle completion of background query
if st.session_state.query_future and st.session_state.query_future.done():
    try:
        result = st.session_state.query_future.result()
        st.session_state.query_result = result
        if result.success:
            history_manager.add_entry(
                st.session_state.last_engine_name.lower(),
                st.session_state.executed_query,
                st.session_state.path_input,
            )
    except Exception as e:
        st.session_state.query_result = QueryResult(success=False, error_message=str(e))

    st.session_state.is_running = False
    st.session_state.query_future = None
    st.session_state.active_engine = None
    st.rerun()

if run_button and st.session_state.path_input:
    if engine_name == "DuckDB":
        engine = DuckDBEngine()
    else:
        engine = SparkEngine()

    # Map dialects
    dialect_mapping = {"DuckDB": "duckdb", "Spark": "spark", "Azure SQL": "tsql"}
    input_dialect_key = dialect_mapping[input_dialect_ui]
    engine_dialect_key = dialect_mapping[engine_name]

    query_to_run = query_text
    translation_error = None

    # Translate query if the input dialect is different from the execution engine
    if input_dialect_key != engine_dialect_key:
        try:
            query_to_run = translator.translate(
                query_text, from_dialect=input_dialect_key, to_dialect=engine_dialect_key
            )
        except Exception as e:
            translation_error = str(e)

    if translation_error:
        st.session_state.query_result = QueryResult(
            success=False,
            error_message=f"Failed to translate input query from {input_dialect_ui} to {engine_name}:\n{translation_error}",
        )
    else:
        st.session_state.is_running = True
        st.session_state.query_result = None
        st.session_state.executed_query = query_text
        st.session_state.executed_input_dialect_key = input_dialect_key
        st.session_state.active_engine = engine

        # Submit to executor
        st.session_state.query_future = executor.submit(
            engine.execute, query_to_run, st.session_state.path_input, preview_limit
        )

    st.rerun()

if cancel_button and st.session_state.active_engine:
    st.session_state.active_engine.interrupt()
    if st.session_state.query_future:
        st.session_state.query_future.cancel()

    st.session_state.is_running = False
    st.session_state.query_future = None
    st.session_state.active_engine = None
    st.warning("Query cancelled.")
    st.rerun()

# --- Results Display ---
if st.session_state.query_result:
    result: QueryResult = st.session_state.query_result

    if result.success:
        # --- Translation Section ---
        st.divider()
        col_t1, col_t2 = st.columns([0.7, 0.3])
        with col_t1:
            st.subheader("SQL Translation")
        with col_t2:
            # All available dialects
            all_dialects_map = {"DuckDB": "duckdb", "Spark": "spark", "Azure SQL": "tsql"}

            # Map the EXECUTED input dialect to key for consistent translation logic
            executed_input_key = st.session_state.executed_input_dialect_key

            # Determine target options: everything except the EXECUTED input dialect
            target_options = [
                ui_name for ui_name, key in all_dialects_map.items() if key != executed_input_key
            ]

            selected_target_ui = st.selectbox(
                "Target Dialect", options=target_options, label_visibility="collapsed"
            )

            # Map UI selection to SQLGlot dialect identifiers
            target_dialect = all_dialects_map[selected_target_ui]

        try:
            # Translate from the EXECUTED query and dialect
            translated_sql = translator.translate(
                st.session_state.executed_query,
                from_dialect=executed_input_key,
                to_dialect=target_dialect,
            )
            with st.expander(f"✨ Translated SQL ({selected_target_ui})", expanded=True):
                st.code(translated_sql, language="sql")
        except Exception as e:
            st.warning(f"Translation failed: {str(e)}")

        m1, m2 = st.columns(2)
        if result.is_truncated:
            m1.metric("Rows Previewed", f"{result.row_count:,}")
            st.caption(f"Note: Preview is truncated at {result.row_count} rows.")
        else:
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
