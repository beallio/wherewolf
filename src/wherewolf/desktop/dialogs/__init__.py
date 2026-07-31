"""Desktop dialog abstractions."""

from .file_dialog_service import FakeFileDialogService, FileDialogService, QtFileDialogService

__all__ = ["FakeFileDialogService", "FileDialogService", "QtFileDialogService"]
