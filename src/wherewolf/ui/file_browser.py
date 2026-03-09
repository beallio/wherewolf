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
        # Custom CSS for compact file explorer buttons
        st.markdown(
            """
            <style>
            .element-container:has(button[key^="dir_"]), 
            .element-container:has(button[key^="file_"]) {
                margin-bottom: -15px;
            }
            .stButton > button {
                font-size: 12px !important;
                padding: 2px 10px !important;
                height: 28px !important;
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
        if col_up.button("⬆️ Up", key="explorer_up"):
            st.session_state.explorer_path = str(current_path.parent)
            st.rerun()
        if col_home.button("🏠 Home", key="explorer_home"):
            st.session_state.explorer_path = str(Path.home())
            st.rerun()

        try:
            items = sorted(os.listdir(current_path))
            # Filter for hidden files if requested
            if not show_hidden:
                items = [i for i in items if not i.startswith(".")]

            valid_exts = {".csv", ".parquet", ".json"}

            for item in items:
                full_path = current_path / item
                if full_path.is_dir():
                    if st.button(f"📁 {item}", key=f"dir_{item}", use_container_width=True):
                        st.session_state.explorer_path = str(full_path)
                        st.rerun()
                elif full_path.suffix.lower() in valid_exts:
                    if st.button(f"📄 {item}", key=f"file_{item}", use_container_width=True):
                        return str(full_path)
        except Exception as e:
            st.error(f"Error reading directory: {e}")

        return None
