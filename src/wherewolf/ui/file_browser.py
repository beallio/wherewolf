import streamlit as st
from pathlib import Path
from typing import Optional
from st_file_browser import st_file_browser


class FileBrowser:
    """A professional file explorer using st-file-browser."""

    @staticmethod
    def render_explorer(show_hidden: bool = False) -> Optional[str]:
        """Renders the st-file-browser component with error handling.

        Args:
            show_hidden: Whether to show hidden files.

        Returns:
            The selected file path if one was clicked, else None.
        """
        if "explorer_path" not in st.session_state:
            st.session_state.explorer_path = str(Path.cwd())

        current_path = Path(st.session_state.explorer_path)

        # Pre-emptive check: If path doesn't exist, reset to CWD
        if not current_path.exists() or not current_path.is_dir():
            st.error(f"❌ Path invalid or inaccessible: `{current_path}`")
            if st.button("🔄 Reset to Current Directory"):
                st.session_state.explorer_path = str(Path.cwd())
                st.rerun()
            return None

        # Re-add navigation buttons for upward movement
        st.write(f"📂 `{current_path}`")
        col_up, col_home = st.columns(2)
        if col_up.button("⬆️ Up", key="st_fb_up", use_container_width=True):
            st.session_state.explorer_path = str(current_path.parent)
            st.rerun()
        if col_home.button("🏠 Home", key="st_fb_home", use_container_width=True):
            st.session_state.explorer_path = str(Path.home())
            st.rerun()

        # Supported data file extensions
        valid_exts = [".csv", ".parquet", ".json"]

        try:
            event = st_file_browser(
                str(current_path),
                # Use a dynamic key to force the component to re-render when the path changes
                key=f"st_file_browser_{current_path}",
                show_choose_file=True,
                # Using flat glob '*' instead of '**/*' to prevent the library from
                # walking the entire tree and crashing on broken symlinks in subfolders.
                glob_patterns=("*",) if show_hidden else ("[!.]*",),
            )
        except Exception as e:
            st.error(
                f"⚠️ Error browsing `{current_path.name}`: Broken links or permission issues detected."
            )
            with st.expander("Technical Details"):
                st.code(str(e))
            if st.button("📂 Go Back"):
                st.session_state.explorer_path = str(current_path.parent)
                st.rerun()
            return None

        if event:
            if event["type"] == "SELECT_FILE":
                selected_item = event["target"]
                # item['path'] is relative to the root provided
                full_path = current_path / selected_item["path"]

                if full_path.suffix.lower() in valid_exts:
                    return str(full_path)
                else:
                    st.warning(f"Unsupported file type: {full_path.suffix}")

        return None
