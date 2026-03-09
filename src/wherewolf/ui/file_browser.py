import tkinter as tk
from tkinter import filedialog
from typing import Optional


class FileBrowser:
    """Utility for native file browsing."""

    @staticmethod
    def select_file() -> Optional[str]:
        """Opens a native file dialog to select a file.

        Returns:
            The selected file path or None.
        """
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            file_path = filedialog.askopenfilename(
                title="Select Dataset",
                filetypes=[
                    ("Data files", "*.parquet *.csv *.json"),
                    ("Parquet files", "*.parquet"),
                    ("CSV files", "*.csv"),
                    ("JSON files", "*.json"),
                    ("All files", "*.*"),
                ],
            )
            root.destroy()
            return file_path if file_path else None
        except Exception:
            return None

    @staticmethod
    def select_directory() -> Optional[str]:
        """Opens a native file dialog to select a directory.

        Returns:
            The selected directory path or None.
        """
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            dir_path = filedialog.askdirectory(title="Select Dataset Directory")
            root.destroy()
            return dir_path if dir_path else None
        except Exception:
            return None
