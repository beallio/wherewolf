import os
import streamlit as st
from pathlib import Path
from typing import Optional


class FileBrowser:
    """A highly resilient, selectbox-based file explorer."""

    @staticmethod
    def _update_dir(key: str):
        """Callback to update the current directory based on selection."""
        # Use session_state directly to avoid stale variable issues
        choice = st.session_state[key]
        curr_dir_key = f"{key}_curr_dir"

        curr_dir = st.session_state[curr_dir_key]

        # Resolve the new path
        if choice == "..":
            new_path = os.path.dirname(curr_dir)
        else:
            new_path = os.path.join(curr_dir, choice)

        new_path = os.path.normpath(new_path)

        # Only update if the selection is actually a directory
        if os.path.isdir(new_path):
            st.session_state[curr_dir_key] = new_path

    @staticmethod
    def render_explorer(show_hidden: bool = False) -> Optional[str]:
        """Renders the selectbox-based file explorer.

        Args:
            show_hidden: Whether to show files/folders starting with '.'.

        Returns:
            The selected file path if one was clicked, else None.
        """
        key = "wherewolf_fs"
        curr_dir_key = f"{key}_curr_dir"
        files_key = f"{key}_files"

        # Initialization
        if curr_dir_key not in st.session_state:
            base_path = str(Path.home())
            st.session_state[curr_dir_key] = base_path

        current_path = st.session_state[curr_dir_key]

        # Re-build files list on every render to respect show_hidden toggle
        try:
            raw_items = sorted(os.listdir(current_path))
            if not show_hidden:
                raw_items = [f for f in raw_items if not f.startswith(".")]

            # Remove '..' if we are at root
            if current_path == os.path.abspath(os.sep):
                files = ["Select file/folder..."] + raw_items
            else:
                files = ["Select file/folder...", ".."] + raw_items

            st.session_state[files_key] = files
        except Exception as e:
            st.error(f"Error reading directory {current_path}: {e}")
            st.session_state[files_key] = ["Select file/folder...", ".."]

        # --- UI Navigation ---
        st.write(f"📂 `{current_path}`")

        selected_file = st.selectbox(
            label="Select file or directory",
            options=st.session_state[files_key],
            key=key,
            on_change=lambda: FileBrowser._update_dir(key),
            help="Select a directory to enter it, or a file to load it.",
            index=0,  # Always reset to placeholder after a change triggers rerun
        )

        if selected_file == "Select file/folder...":
            return None

        full_path = os.path.normpath(os.path.join(current_path, selected_file))

        # --- Contextual Actions ---
        if os.path.isdir(full_path):
            st.caption("📁 *Directory selected. Change selection to enter.*")
        else:
            # Display file info
            valid_exts = {".csv", ".parquet", ".json", ".xlsx", ".xls"}
            is_valid = Path(full_path).suffix.lower() in valid_exts

            if is_valid:
                st.success(f"📄 Ready to load: `{selected_file}`")
                if st.button("🚀 Load This File", width="stretch", type="primary"):
                    return full_path
            else:
                st.warning(f"⚠️ `{selected_file}` is not a supported data format.")

        return None
