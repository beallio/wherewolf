from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtWidgets import QFileDialog, QWidget

from wherewolf.desktop.dialogs.file_dialog_service import (
    FileDialogService,
    QtFileDialogService,
    normalise_sql_destination,
)
from wherewolf.domain.enums import SourceFormat
from wherewolf.services.export_destination import ExportFormat


class FakeFileDialogService:
    def __init__(self, paths: tuple[Path, ...]) -> None:
        self.paths = paths
        self.called_with: dict[str, Any] = {}

    def choose_dataset_files(
        self, default_directory: Path | None, parent: QWidget | None = None
    ) -> tuple[Path, ...]:
        self.called_with = {
            "default_directory": default_directory,
            "parent_is_none": parent is None,
        }
        return self.paths

    def choose_value_counts_path(
        self,
        default_directory: Path | None,
        export_format: ExportFormat,
        parent: QWidget | None = None,
    ) -> Path | None:
        del default_directory, export_format, parent
        return None

    def choose_sql_open_path(
        self, default_directory: Path | None, parent: QWidget | None = None
    ) -> Path | None:
        del default_directory, parent
        return None

    def choose_sql_save_path(
        self, default_directory: Path | None, parent: QWidget | None = None
    ) -> Path | None:
        del default_directory, parent
        return None

    def choose_directory(
        self, default_directory: Path | None, parent: QWidget | None = None
    ) -> Path | None:
        del default_directory, parent
        return None


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
def test_qt_file_dialog_service_cancellation_is_empty_tuple(
    monkeypatch, default_directory: Path | None
) -> None:
    monkeypatch.setattr(
        "wherewolf.desktop.dialogs.file_dialog_service.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: ([], ""),
    )

    service = QtFileDialogService()
    assert service.choose_dataset_files(default_directory) == ()


def test_qt_file_dialog_service_initial_filter_matches_built_filter(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def get_open_file_names(*_args, **kwargs):
        captured.update(kwargs)
        return [], ""

    monkeypatch.setattr(
        "wherewolf.desktop.dialogs.file_dialog_service.QFileDialog.getOpenFileNames",
        get_open_file_names,
    )

    service = QtFileDialogService()
    service.choose_dataset_files(None)

    assert captured["initialFilter"] == service._build_filter()


def test_qt_file_dialog_service_show_hidden_uses_hidden_file_filter(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Dialog:
        def setFileMode(self, _mode):
            pass

        def setNameFilter(self, _filter):
            pass

        def setDirectory(self, _directory):
            pass

        def setOption(self, _option):
            pass

        def setFilter(self, file_filter):
            captured["filter"] = file_filter

        def exec(self):
            return False

        def selectedFiles(self):
            return []

    class DialogFactory:
        FileMode = QFileDialog.FileMode
        Option = QFileDialog.Option

        def __call__(self, *_args, **_kwargs):
            return Dialog()

    monkeypatch.setattr(
        "wherewolf.desktop.dialogs.file_dialog_service.QFileDialog", DialogFactory()
    )
    assert QtFileDialogService().choose_dataset_files(None, show_hidden=True) == ()
    assert captured["filter"]


def test_qt_export_dialog_cancellation_returns_none_without_creating_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "cancelled.csv"
    monkeypatch.setattr(
        "wherewolf.desktop.dialogs.file_dialog_service.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )

    service = QtFileDialogService()

    assert service.choose_export_path(tmp_path, ExportFormat.CSV) is None
    assert not destination.exists()


@pytest.mark.parametrize(
    ("chosen", "expected"),
    [
        ("/tmp/history", "/tmp/history.sql"),
        ("/tmp/history.sql", "/tmp/history.sql"),
        ("/tmp/history.txt", "/tmp/history.txt"),
    ],
)
def test_normalise_sql_destination_preserves_user_supplied_suffix(
    chosen: str, expected: str
) -> None:
    assert normalise_sql_destination(Path(chosen)) == Path(expected)


@pytest.mark.parametrize(
    ("chosen", "expected"),
    [
        ("/tmp/history", "/tmp/history.sql"),
        ("/tmp/history.sql", "/tmp/history.sql"),
        ("/tmp/history.txt", "/tmp/history.txt"),
    ],
)
def test_qt_history_sql_path_appends_suffix(
    monkeypatch: pytest.MonkeyPatch, chosen: str, expected: str
) -> None:
    monkeypatch.setattr(
        "wherewolf.desktop.dialogs.file_dialog_service.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (chosen, ""),
    )

    assert QtFileDialogService().choose_history_sql_path(None) == Path(expected)


def test_qt_history_sql_path_cancellation_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "wherewolf.desktop.dialogs.file_dialog_service.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )

    assert QtFileDialogService().choose_history_sql_path(None) is None


@pytest.mark.parametrize(
    ("chosen", "expected"),
    [("/tmp/library", Path("/tmp/library")), ("", None)],
)
def test_qt_choose_directory_returns_the_selected_folder(
    monkeypatch: pytest.MonkeyPatch, chosen: str, expected: Path | None
) -> None:
    monkeypatch.setattr(
        "wherewolf.desktop.dialogs.file_dialog_service.QFileDialog.getExistingDirectory",
        lambda *_args, **_kwargs: chosen,
    )

    assert QtFileDialogService().choose_directory(None) == expected


def test_fake_choose_directory_returns_its_configured_folder() -> None:
    from wherewolf.desktop.dialogs.file_dialog_service import (
        FakeFileDialogService as PackagedFake,
    )

    service = PackagedFake((), directory=Path("/tmp/library"))

    assert service.choose_directory(None) == Path("/tmp/library")
    assert PackagedFake(()).choose_directory(Path("/tmp")) is None
