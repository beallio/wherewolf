"""Desktop widget primitives used by the PyQt shell."""

from .catalog_dock import CatalogDock
from .folder_column_delegate import FolderColumnDelegate
from .history_dock import HistoryDock
from .sql_editor import SqlEditor

__all__ = ["CatalogDock", "FolderColumnDelegate", "HistoryDock", "SqlEditor"]
