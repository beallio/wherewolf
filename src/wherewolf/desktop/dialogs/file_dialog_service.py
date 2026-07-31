"""Desktop dialog adapters and protocol."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing_extensions import Protocol, runtime_checkable

from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QFileDialog

from wherewolf.domain.enums import SourceFormat


@runtime_checkable
class FileDialogService(Protocol):
    def choose_dataset_files(self, default_directory: Path | None, parent: QWidget | None = None) -> tuple[Path, ...]:
        """Ask the user for one or more dataset files."""


@dataclass(frozen=True)
class FakeFileDialogService:
    paths: tuple[Path, ...]

    def choose_dataset_files(self, default_directory: Path | None, parent: QWidget | None = None) -> tuple[Path, ...]:
        del default_directory, parent
        return self.paths


class QtFileDialogService:
    """Production dialog wrapper for dataset file selection."""

    def choose_dataset_files(self, default_directory: Path | None, parent: QWidget | None = None) -> tuple[Path, ...]:
        parent_window = parent
        directory = str(default_directory) if default_directory is not None else ""
        names, _ = QFileDialog.getOpenFileNames(
            parent_window,
            caption="Select datasets",
            directory=directory,
            filter=self._build_filter(),
            options=QFileDialog.Option.ReadOnly,
            selectedFilter="Supported files (*.csv *.parquet *.json *.jsonl *.xlsx)",
        )
        return tuple(Path(name) for name in names)

    @staticmethod
    def _build_filter() -> str:
        formats = " ".join(f"*.{source_format.value}" for source_format in SourceFormat)
        return f"Supported files ({formats})"
