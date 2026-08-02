"""Guards for two ways an export could quietly cost the user data.

1. `registry._source_warnings` detects that a source file changed underneath a full
   export, and `ExportController` carries those warnings out on `ExportResult`. Nothing
   displayed them, so the app reported plain success over a stale-source export.

2. The export destination dialog passed `DontConfirmOverwrite`, so choosing an existing
   filename silently destroyed it — while the migration plan promised confirmation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QFileDialog

from wherewolf.desktop.dialogs.file_dialog_service import QtFileDialogService
from wherewolf.desktop.export_controller import ExportResult
from wherewolf.desktop.main_window import MainWindow
from wherewolf.services.export_destination import ExportFormat


@pytest.fixture
def window(qtbot) -> MainWindow:
    win = MainWindow()
    qtbot.addWidget(win)
    return win


def _capture_status(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every status message the window emits."""
    shown: list[str] = []

    def record(message: str, timeout: int = 3000) -> None:
        shown.append(message)

    monkeypatch.setattr(window, "_show_status", record)
    return shown


def test_successful_export_reports_source_warnings(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A changed source file must not be reported as an unqualified success."""
    shown = _capture_status(window, monkeypatch)

    window._on_export_result(
        ExportResult(
            destination=Path("/tmp/out.csv"),
            succeeded=True,
            warnings=("data.csv changed on disk since the query ran",),
        )
    )

    combined = "\n".join(shown)
    assert "changed on disk" in combined, (
        f"export warnings were computed but never surfaced; status showed: {shown!r}"
    )


def test_successful_export_without_warnings_still_reports_the_destination(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The warning path must not swallow the ordinary success message."""
    shown = _capture_status(window, monkeypatch)

    window._on_export_result(ExportResult(destination=Path("/tmp/out.csv"), succeeded=True))

    combined = "\n".join(shown)
    assert "/tmp/out.csv" in combined
    assert "warning" not in combined.lower()


def test_export_destination_dialog_confirms_overwrite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Qt must be allowed to prompt before an existing file is replaced."""
    captured: list[tuple[object, ...]] = []

    def fake_get_save_file_name(*args: object, **kwargs: object) -> tuple[str, str]:
        captured.append(args)
        return ("", "")

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_get_save_file_name)

    QtFileDialogService().choose_export_path(
        default_directory=Path("/tmp"),
        export_format=ExportFormat.CSV,
        parent=None,
    )

    options = [a for a in captured[0] if isinstance(a, QFileDialog.Option)]
    assert all(QFileDialog.Option.DontConfirmOverwrite not in opt for opt in options), (
        "DontConfirmOverwrite suppresses the native overwrite prompt, so an export "
        "silently destroys an existing file"
    )
