import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class HistoryManager:
    """Manages local query history persistence."""

    DEFAULT_PATH = Path.home() / ".wherewolf" / "history.json"

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or self.DEFAULT_PATH
        self._ensure_storage()

    def _ensure_storage(self):
        """Ensures the storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            with open(self.storage_path, "w") as f:
                json.dump([], f)

    def add_entry(self, engine: str, query: str, path: str):
        """Adds a new query to the history.

        Args:
            engine: The execution engine used (e.g., 'duckdb').
            query: The SQL query string.
            path: The dataset path used.
        """
        import os
        import tempfile

        history = self.get_all()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "engine": engine,
            "query": query,
            "path": path,
        }
        history.insert(0, entry)  # Add to the beginning

        # Limit history to 100 entries
        history = history[:100]

        # Atomic write using a temporary file
        temp_fd, temp_path = tempfile.mkstemp(dir=self.storage_path.parent, text=True)
        try:
            with os.fdopen(temp_fd, "w") as f:
                json.dump(history, f, indent=2)
            os.replace(temp_path, self.storage_path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def get_all(self) -> List[Dict]:
        """Returns all history entries.

        Returns:
            A list of history entry dictionaries.
        """
        try:
            if not self.storage_path.exists():
                return []
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # If corrupted, we might want to be more careful, but for now returning empty
            # is what the previous implementation did.
            return []

    def clear(self):
        """Clears the query history."""
        import os
        import tempfile

        temp_fd, temp_path = tempfile.mkstemp(dir=self.storage_path.parent, text=True)
        try:
            with os.fdopen(temp_fd, "w") as f:
                json.dump([], f)
            os.replace(temp_path, self.storage_path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
