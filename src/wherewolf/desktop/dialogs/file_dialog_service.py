"""Desktop dialog adapters and protocol."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from PyQt6.QtCore import QDir
from PyQt6.QtWidgets import QFileDialog, QWidget

from wherewolf.domain.enums import SourceFormat
from wherewolf.services.export_destination import (
    export_file_filter,
    normalise_destination,
)


@runtime_checkable
class FileDialogService(Protocol):
    def choose_dataset_files(
        self,
        default_directory: Path | None,
        parent: QWidget | None = None,
    ) -> tuple[Path, ...]:
        """Ask the user for one or more dataset files."""


@dataclass(frozen=True)
class FakeFileDialogService:
    paths: tuple[Path, ...]
    export_path: Path | None = None

    def choose_dataset_files(
        self,
        default_directory: Path | None,
        parent: QWidget | None = None,
        show_hidden: bool = False,
    ) -> tuple[Path, ...]:
        del default_directory, parent, show_hidden
        return self.paths

    def choose_export_path(self, default_directory, export_format, parent=None) -> Path | None:
        del default_directory, parent
        return normalise_destination(self.export_path, export_format) if self.export_path else None


class QtFileDialogService:
    """Production dialog wrapper for dataset file selection."""

    def choose_dataset_files(
        self,
        default_directory: Path | None,
        parent: QWidget | None = None,
        show_hidden: bool = False,
    ) -> tuple[Path, ...]:
        parent_window = parent
        directory = str(default_directory) if default_directory is not None else ""
        if show_hidden:
            dialog = QFileDialog(parent_window, "Select datasets", directory, self._build_filter())
            dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
            dialog.setNameFilter(self._build_filter())
            dialog.setDirectory(directory)
            dialog.setOption(QFileDialog.Option.ReadOnly)
            dialog.setFilter(QDir.Filter.Files | QDir.Filter.Hidden)
            if not dialog.exec():
                return ()
            return tuple(Path(name) for name in dialog.selectedFiles())
        names, _ = QFileDialog.getOpenFileNames(
            parent_window,
            caption="Select datasets",
            directory=directory,
            filter=self._build_filter(),
            options=QFileDialog.Option.ReadOnly,
            initialFilter="Supported files (*.csv *.parquet *.json *.jsonl *.xlsx)",
        )
        return tuple(Path(name) for name in names)

    def choose_export_path(self, default_directory, export_format, parent=None) -> Path | None:
        name, _ = QFileDialog.getSaveFileName(
            parent,
            "Export results",
            str(default_directory or ""),
            export_file_filter(export_format),
            f"*.{export_format.value}",
            # No DontConfirmOverwrite: let the native dialog prompt before replacing an
            # existing file. Suppressing it made exports destroy files silently.
        )
        return normalise_destination(Path(name), export_format) if name else None

    @staticmethod
    def _build_filter() -> str:
        formats = " ".join(f"*.{source_format.value}" for source_format in SourceFormat)
        return f"Supported files ({formats})"
