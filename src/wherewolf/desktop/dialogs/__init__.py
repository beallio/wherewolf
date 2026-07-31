"""Desktop dialog abstractions."""

from .file_dialog_service import FileDialogService, FakeFileDialogService, QtFileDialogService

__all__ = ["FileDialogService", "FakeFileDialogService", "QtFileDialogService"]
