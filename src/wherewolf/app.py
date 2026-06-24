import streamlit as st
import os
from concurrent.futures import ThreadPoolExecutor
from wherewolf.execution import QueryResult
from wherewolf.translation import Translator
from wherewolf.storage import HistoryManager
from wherewolf.ui import FileBrowser, ResultsView
from wherewolf.constants import DIALECT_MAPPING
from wherewolf.engines import get_engine, get_duckdb_engine, get_spark_engine  # noqa: F401
from streamlit_ace import st_ace
import importlib.metadata

# Get version from metadata
try:
    __version__ = importlib.metadata.version("wherewolf")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.5.0"  # Fallback for dev runs

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

            /* Darken and widen the sidebar */
            [data-testid="stSidebar"] {
                background-color: #000000;
                min-width: 450px !important;
                max-width: 450px !important;
            }

            /* Add back some top padding for main content */
            .main .block-container, .block-container {
                padding-top: 4rem !important;
                margin-top: 0rem !important;
            }

            /* Aggressively remove top padding for sidebar */
            [data-testid="stSidebar"] section {
                padding-top: 0rem !important;
            }
            [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
                padding-top: 0rem !important;
            }
            /* Specific fix for sidebar header whitespace */
            [data-testid="stSidebarHeader"], .st-emotion-cache-10p9htt {
                height: 3rem !important;
                min-height: 3rem !important;
                margin-bottom: 0rem !important;
                padding-top: 0rem !important;
            }

            /* Make primary buttons green */
            button[kind="primary"] {
                background-color: #28a745 !important;
                border-color: #28a745 !important;
                color: white !important;
            }
            button[kind="primary"]:hover {
                background-color: #218838 !important;
                border-color: #1e7e34 !important;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)


@st.cache_resource
def get_executor():
    return ThreadPoolExecutor(max_workers=4)


if "editor_reset_counter" not in st.session_state:
    st.session_state.editor_reset_counter = 0

executor = get_executor()

# --- Initialize Session State ---
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
if "executed_engine_query" not in st.session_state:
    st.session_state.executed_engine_query = ""
if "executed_engine_name" not in st.session_state:
    st.session_state.executed_engine_name = "DuckDB"
if "full_export" not in st.session_state:
    st.session_state.full_export = None
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

if "catalog" not in st.session_state:
    st.session_state.catalog = {}  # alias -> path
if "schema_focus" not in st.session_state:
    st.session_state.schema_focus = None


def sanitize_alias(name: str) -> str:
    """Sanitizes a string to be a valid SQL identifier."""
    import re

    # Force start with letter/underscore, only alphanumeric/underscore
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not name or not name[0].isalpha() and name[0] != "_":
        name = "t_" + name
    # Block common keywords (basic check)
    reserved = {
        "SELECT",
        "FROM",
        "WHERE",
        "JOIN",
        "UNION",
        "GROUP",
        "ORDER",
        "LIMIT",
        "TABLE",
        "VIEW",
    }
    if name.upper() in reserved:
        name = name + "_alias"
    return name


def get_default_alias(path: str) -> str:
    """Derives a default alias from the path with collision handling."""
    from pathlib import Path

    p = Path(path)
    stem = sanitize_alias(p.stem)

    # Priority 1: Stem
    if stem not in st.session_state.catalog:
        return stem

    # Priority 2: Full filename with extension as suffix
    fullname = sanitize_alias(p.name.replace(".", "_"))
    if fullname not in st.session_state.catalog:
        return fullname

    # Priority 3: Stem + counter
    counter = 1
    while f"{stem}_{counter}" in st.session_state.catalog:
        counter += 1
    return f"{stem}_{counter}"


# --- Early State Update Pattern ---
# This avoids StreamlitAPIException by updating state BEFORE widgets are instantiated.
if "pending_query" in st.session_state:
    st.session_state.selected_query = st.session_state.pending_query
    if "editor_reset_counter" in st.session_state:
        st.session_state.editor_reset_counter += 1
    del st.session_state.pending_query

if "pending_catalog" in st.session_state:
    st.session_state.catalog = st.session_state.pending_catalog
    del st.session_state.pending_catalog

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
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px; position: relative;">
            <img src="data:image/png;base64,{logo_b64}" width="60">
            <div>
                <h1 style="margin: 0; white-space: nowrap; font-size: 2.2rem;">Wherewolf</h1>
                <p style="margin: 0; font-size: 0.8rem; color: #666; position: absolute; bottom: -12px; left: 72px;">v{__version__}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. CATALOG MANAGEMENT
    with st.expander("📁 Manage Dataset Catalog", expanded=True):
        st.caption("Browse and add files to your SQL namespace.")
        show_hidden = st.checkbox("Show Hidden Files", value=False)
        selected_path = FileBrowser.render_explorer(show_hidden=show_hidden)

        if selected_path:
            # Determine alias and add
            alias = get_default_alias(selected_path)

            # If this is the FIRST dataset, update the default query
            if not st.session_state.catalog:
                query = f"SELECT * FROM {alias} LIMIT 10"
                st.session_state.selected_query = query
                # Increment counter to force st_ace to re-mount with new value
                if "editor_reset_counter" in st.session_state:
                    st.session_state.editor_reset_counter += 1

            st.session_state.catalog[alias] = selected_path
            st.session_state.schema_focus = alias

            st.success(f"Added `{alias}` to catalog.")
            st.rerun()

    if st.session_state.catalog:
        st.subheader("Active Catalog")
        for alias in list(st.session_state.catalog.keys()):
            col_a, col_r = st.columns([0.8, 0.2])
            col_a.code(f"{alias}", language="sql")
            if col_r.button("🗑️", key=f"remove_{alias}", help=f"Remove {alias}"):
                del st.session_state.catalog[alias]
                if st.session_state.schema_focus == alias:
                    st.session_state.schema_focus = (
                        list(st.session_state.catalog.keys())[0]
                        if st.session_state.catalog
                        else None
                    )
                st.rerun()
            st.caption(f"`{st.session_state.catalog[alias]}`")
    else:
        st.warning("⚠️ No datasets loaded.")

    engine_name = st.selectbox("Execution Engine", ["DuckDB", "Spark"])

    # --- Schema HUD Logic ---
    if st.session_state.catalog:
        # Selector for which schema to focus on
        schema_options = list(st.session_state.catalog.keys())
        if st.session_state.schema_focus not in schema_options:
            st.session_state.schema_focus = schema_options[0]

        focus_alias = st.selectbox(
            "Metadata Focus",
            options=schema_options,
            index=schema_options.index(st.session_state.schema_focus),
        )
        st.session_state.schema_focus = focus_alias
        focus_path = st.session_state.catalog[focus_alias]

        # Refresh schema if path or engine changed
        if (
            focus_path != st.session_state.last_schema_path
            or engine_name != st.session_state.last_schema_engine
        ):
            try:
                temp_engine = get_engine(engine_name)
                st.session_state.schema = temp_engine.get_schema(focus_path)
                st.session_state.last_schema_path = focus_path
                st.session_state.last_schema_engine = engine_name
            except Exception as e:
                st.session_state.schema = None
                st.sidebar.error(f"Failed to fetch schema: {e}")

        if st.session_state.schema is not None and not st.session_state.schema.is_empty():
            with st.expander(f"📊 {focus_alias} Schema", expanded=True):
                st.dataframe(
                    st.session_state.schema,
                    hide_index=True,
                    width="stretch",
                    height=200,
                )
        elif st.session_state.schema is not None:
            st.caption("No columns detected.")

    # Auto-align input dialect if engine changes
    if st.session_state.last_engine_name != engine_name:
        st.session_state.input_dialect_ui = engine_name
        st.session_state.last_engine_name = engine_name

    preview_limit = st.slider("Preview Size", 10, 1000, 100)

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
            st.session_state.pending_catalog = history[idx]["catalog"]
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

# Use a container-like column to force alignment of editor and buttons
main_col, _ = st.columns([0.99, 0.01])
with main_col:
    # Dialect selector right-aligned within the main column
    _, col_h2 = st.columns([0.7, 0.3])
    with col_h2:
        input_dialect_ui = st.selectbox(
            "Input Dialect", options=["DuckDB", "Spark", "Azure SQL"], key="input_dialect_ui"
        )

    # Use st_ace for syntax highlighting
    # Use a dynamic key based on selected_query to force re-render when the query is updated programmatically
    # But we want to maintain the same key for user typing, so we only change it when we WANT to force a reset.
    # Actually, a better way is to use a specific reset key in session state.
    query_text = st_ace(
        value=st.session_state.selected_query,
        language="sql",
        theme=ace_theme,
        height=300,
        key=f"sql_editor_{st.session_state.editor_reset_counter}",
        auto_update=True,
    )

    # Button row inside the same alignment context
    col_b1, col_b2, col_b3 = st.columns([0.12, 0.12, 0.76])
    with col_b1:
        run_button = st.button(
            "Run",
            type="primary",
            disabled=st.session_state.is_running or not st.session_state.catalog,
        )
    with col_b2:
        cancel_button = st.button("Cancel", disabled=not st.session_state.is_running)

if run_button and st.session_state.catalog:
    engine = get_engine(engine_name)

    # Map dialects
    input_dialect_key = DIALECT_MAPPING[st.session_state.input_dialect_ui]
    engine_dialect_key = DIALECT_MAPPING[engine_name]

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
            error_message=f"Failed to translate input query from {st.session_state.input_dialect_ui} to {engine_name}:\n{translation_error}",
        )
    else:
        st.session_state.is_running = True
        st.session_state.query_result = None
        st.session_state.executed_query = query_text
        st.session_state.executed_input_dialect_key = input_dialect_key
        # Record the engine-dialect query and engine actually executed so a full
        # export can re-run the exact query without re-translating.
        st.session_state.executed_engine_query = query_to_run
        st.session_state.executed_engine_name = engine_name
        st.session_state.full_export = None
        st.session_state.active_engine = engine

        # Submit to executor
        st.session_state.query_future = executor.submit(
            engine.execute, query_to_run, "", preview_limit, st.session_state.catalog.copy()
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
                "",  # path is deprecated
                catalog=st.session_state.catalog,
            )
    except Exception as e:
        st.session_state.query_result = QueryResult(success=False, error_message=str(e))

    st.session_state.is_running = False
    st.session_state.query_future = None
    st.session_state.active_engine = None
    st.rerun()

# --- Results Display ---
if st.session_state.query_result:
    ResultsView.render(st.session_state.query_result, translator, get_engine)
elif not st.session_state.catalog:
    st.info("👈 Please add a dataset to the catalog in the sidebar to begin.")

# --- Autorefresh while running ---
if st.session_state.is_running and "PYTEST_CURRENT_TEST" not in os.environ:
    import time

    time.sleep(0.1)
    st.rerun()
