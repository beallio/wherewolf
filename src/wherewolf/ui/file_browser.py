import os
import streamlit as st
from pathlib import Path
from typing import Optional


class FileBrowser:
    """A resilient, Streamlit-native file explorer with customization."""

    @staticmethod
    def render_explorer(show_hidden: bool = False) -> Optional[str]:
        """Renders a simple file explorer in the Streamlit UI.

        Args:
            show_hidden: Whether to show files/folders starting with '.'.

        Returns:
            The selected file path if one was clicked, else None.
        """
        # Custom CSS for compact, left-aligned file explorer buttons
        st.markdown(
            """
            <style>
            /* Reduce vertical spacing between buttons */
            .element-container:has(button[key^="dir_"]), 
            .element-container:has(button[key^="file_"]) {
                margin-bottom: -15px !important;
            }
            /* Force left alignment and compact styling */
            .stButton > button {
                font-size: 13px !important;
                padding: 2px 8px !important;
                height: 30px !important;
                justify-content: flex-start !important;
                text-align: left !important;
                width: 100% !important;
                display: flex !important;
                border: none !important;
                background-color: transparent !important;
            }
            .stButton > button:hover {
                background-color: rgba(151, 166, 195, 0.1) !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        if "explorer_path" not in st.session_state:
            st.session_state.explorer_path = str(Path.cwd())

        current_path = Path(st.session_state.explorer_path)

        st.write(f"📂 `{current_path}`")

        col_up, col_home = st.columns(2)
        if col_up.button("⬆️ Up", key="explorer_up", use_container_width=True):
            st.session_state.explorer_path = str(current_path.parent)
            st.rerun()
        if col_home.button("🏠 Home", key="explorer_home", use_container_width=True):
            st.session_state.explorer_path = str(Path.home())
            st.rerun()

        try:
            raw_items = os.listdir(current_path)
            if not show_hidden:
                raw_items = [i for i in raw_items if not i.startswith(".")]

            # Separate and sort: Dirs first, then Files
            dirs = []
            files = []
            valid_exts = {".csv", ".parquet", ".json"}

            for item in raw_items:
                full_path = current_path / item
                try:
                    if full_path.is_dir():
                        dirs.append(item)
                    elif full_path.suffix.lower() in valid_exts:
                        files.append(item)
                except (PermissionError, OSError):
                    continue

            dirs.sort(key=str.lower)
            files.sort(key=str.lower)

            # Render Directories
            for d in dirs:
                if st.button(f"📁 {d}", key=f"dir_{d}", use_container_width=True):
                    st.session_state.explorer_path = str(current_path / d)
                    st.rerun()

            # Render Files
            for f in files:
                if st.button(f"📄 {f}", key=f"file_{f}", use_container_width=True):
                    return str(current_path / f)

        except Exception as e:
            st.error(f"Error reading directory: {e}")

        return None
