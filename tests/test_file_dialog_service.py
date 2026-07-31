from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtWidgets import QWidget

from wherewolf.desktop.dialogs.file_dialog_service import (
    FileDialogService,
    QtFileDialogService,
)
from wherewolf.domain.enums import SourceFormat


class FakeFileDialogService:
    def __init__(self, paths: tuple[Path, ...]) -> None:
        self.paths = paths
        self.called_with: dict[str, Any] = {}

    def choose_dataset_files(self, default_directory: Path | None, parent: QWidget | None = None) -> tuple[Path, ...]:
        self.called_with = {
            "default_directory": default_directory,
            "parent_is_none": parent is None,
        }
        return self.paths


def test_fake_file_dialog_service_protocol_and_cancellation() -> None:
    service: FileDialogService = FakeFileDialogService(())
    assert service.choose_dataset_files(None) == ()


def test_fake_file_dialog_service_resolves_fixed_tuple() -> None:
    paths = (Path("/tmp/a.csv"), Path("/tmp/b.xlsx"))
    service = FakeFileDialogService(paths)
    assert service.choose_dataset_files(Path("/tmp")) == paths


def test_qt_file_dialog_service_filter_is_format_driven() -> None:
    service = QtFileDialogService()
    assert service._build_filter().startswith("Supported files (")
    assert "*.csv" in service._build_filter()
    assert "*.parquet" in service._build_filter()
    assert "*.json" in service._build_filter()
    assert "*.jsonl" in service._build_filter()
    assert "*.xlsx" in service._build_filter()
    assert " *.xls)" not in service._build_filter()
    assert "*.xls " not in service._build_filter()

    for source_format in SourceFormat:
        assert f"*.{source_format.value}" in service._build_filter()


@pytest.mark.parametrize("default_directory", [None, Path("/tmp")])
def test_qt_file_dialog_service_cancellation_is_empty_tuple(monkeypatch, default_directory: Path | None) -> None:
    monkeypatch.setattr(
        "wherewolf.desktop.dialogs.file_dialog_service.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: ([], ""),
    )

    service = QtFileDialogService()
    assert service.choose_dataset_files(default_directory) == ()
