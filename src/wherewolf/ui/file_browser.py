import os
import streamlit as st
from pathlib import Path
from typing import Optional
from wherewolf.constants import SUPPORTED_EXTENSIONS


class FileBrowser:
    """
    A highly resilient, selectbox-based file explorer for Streamlit.

    This component allows users to navigate the local filesystem and select
    files with supported extensions for data analysis. It supports:
    - Directory-first sorting
    - Visual indicators (emojis) for folders and navigation
    - Filtering of files based on application constants
    - Native Streamlit placeholder support
    """

    @staticmethod
    def _update_dir(key: str):
        """
        Callback to update the current directory based on selection.

        Args:
            key: The session state key for the selectbox.
        """
        # Use session_state directly to avoid stale variable issues
        choice = st.session_state.get(key)
        if choice is None:
            return

        curr_dir_key = f"{key}_curr_dir"
        curr_dir = st.session_state[curr_dir_key]

        # Resolve the new path
        if choice == "..":
            # Navigate up
            new_path = os.path.dirname(curr_dir)
        else:
            # Navigate into subdirectory
            new_path = os.path.join(curr_dir, choice)

        new_path = os.path.normpath(new_path)

        # Only update if the selection is actually a directory
        # This prevents the browser from changing directory when a file is selected
        if os.path.isdir(new_path):
            st.session_state[curr_dir_key] = new_path

    @staticmethod
    def render_explorer(show_hidden: bool = False) -> Optional[str]:
        """
        Renders the selectbox-based file explorer.

        Args:
            show_hidden: Whether to show files/folders starting with '.'.

        Returns:
            The selected file path if one was clicked, else None.
        """
        key = "wherewolf_fs"
        curr_dir_key = f"{key}_curr_dir"
        files_key = f"{key}_files"

        # Initialize to home directory if not set
        if curr_dir_key not in st.session_state:
            base_path = str(Path.home())
            st.session_state[curr_dir_key] = base_path

        current_path = st.session_state[curr_dir_key]

        # Re-build files list on every render to respect show_hidden toggle
        try:
            # Get all items and filter out hidden ones if requested
            raw_items = sorted(os.listdir(current_path))
            if not show_hidden:
                raw_items = [f for f in raw_items if not f.startswith(".")]

            # Filter and sort items: always show directories, only show files with supported extensions
            dirs = []
            files = []
            for item in raw_items:
                full_item_path = os.path.join(current_path, item)
                if os.path.isdir(full_item_path):
                    dirs.append(item)
                else:
                    # Check against the centralized list of supported extensions
                    if Path(item).suffix.lower() in SUPPORTED_EXTENSIONS:
                        files.append(item)

            # Combine: directories first (alphabetical), then files (alphabetical)
            filtered_items = dirs + files

            # Build final options list. '..' is added for non-root directories.
            if current_path == os.path.abspath(os.sep):
                options = filtered_items
            else:
                options = [".."] + filtered_items

            st.session_state[files_key] = options
        except Exception as e:
            st.error(f"Error reading directory {current_path}: {e}")
            st.session_state[files_key] = [".."]

        # --- UI Header ---
        st.write(f"📂 `{current_path}`")

        def format_item(item: str) -> str:
            """
            Display formatter for the selectbox.
            Adds icons to directories to distinguish them from files.
            """
            if item == "..":
                return "⤴️ .."

            full_item_path = os.path.join(current_path, item)
            if os.path.isdir(full_item_path):
                return f"📁 {item}"
            return item

        # The main selection widget
        selected_file = st.selectbox(
            label="Select file or directory",
            options=st.session_state[files_key],
            key=key,
            on_change=lambda: FileBrowser._update_dir(key),
            help="Select a directory to enter it, or a file to load it.",
            index=None,  # Do not select anything by default
            placeholder="Select file/folder...",
            format_func=format_item,
        )

        if selected_file is None:
            return None

        # Absolute path for the current selection
        full_path = os.path.normpath(os.path.join(current_path, selected_file))

        # --- Contextual Actions & Validation ---
        if os.path.isdir(full_path):
            st.caption("📁 *Directory selected. Change selection to enter.*")
        else:
            # Final check of extension before enabling the load button
            is_valid = Path(full_path).suffix.lower() in SUPPORTED_EXTENSIONS

            if is_valid:
                st.success(f"📄 Ready to load: `{selected_file}`")
                if st.button("Load This File", width="stretch", type="primary"):
                    return full_path
            else:
                # Fallback warning for edge cases
                st.warning(f"⚠️ `{selected_file}` is not a supported data format.")

        return None
