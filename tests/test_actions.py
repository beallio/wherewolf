from pathlib import Path

from PyQt6.QtGui import QKeySequence

from wherewolf.desktop import DesktopActions, build_actions
from wherewolf.desktop.dialogs import FakeFileDialogService
from wherewolf.desktop.main_window import MainWindow
from wherewolf.services import CatalogService, SettingsService


def test_build_actions_contains_expected_shortcuts_and_states(qapp) -> None:
    actions = build_actions()

    assert isinstance(actions, DesktopActions)
    assert actions.run.text() == "Run"
    assert actions.run.isEnabled()
    assert actions.run.shortcut() == QKeySequence("Ctrl+Return")

    assert actions.cancel.text() == "Cancel"
    assert not actions.cancel.isEnabled()
    assert actions.cancel.shortcut() == QKeySequence("Ctrl+.")

    assert not actions.format_sql.isEnabled()
    assert "Phase 3" in actions.format_sql.toolTip()

    assert actions.add_datasets.isEnabled()
    assert actions.add_datasets.shortcut().toString() == QKeySequence("Ctrl+O").toString()
    assert "Unavailable" not in actions.add_datasets.toolTip()


def test_add_datasets_action_adds_catalog_paths(tmp_path, qtbot) -> None:
    service = CatalogService()
    file_service = FakeFileDialogService((tmp_path / "a.csv", tmp_path / "b.csv"))
    (tmp_path / "a.csv").write_text("a\n1")
    (tmp_path / "b.csv").write_text("a\n1")

    window = MainWindow(catalog_service=service, file_dialog_service=file_service)
    qtbot.addWidget(window)

    window.desktop_actions.add_datasets.trigger()
    assert len(service.snapshot()) == 2


def test_add_datasets_action_noop_when_dialog_cancelled(tmp_path, qtbot) -> None:
    service = CatalogService()
    file_service = FakeFileDialogService(())

    window = MainWindow(catalog_service=service, file_dialog_service=file_service)
    qtbot.addWidget(window)

    window.desktop_actions.add_datasets.trigger()
    assert len(service.snapshot()) == 0


def test_add_datasets_opens_at_last_directory_and_updates_on_success(tmp_path, qtbot) -> None:
    class SpyFileDialogService:
        def __init__(self, paths: tuple[Path, ...], observed: list[Path | None]) -> None:
            self.paths = paths
            self.observed = observed

        def choose_dataset_files(
            self, default_directory: Path | None, parent=None
        ) -> tuple[Path, ...]:
            self.observed.append(default_directory)
            return self.paths

    service = CatalogService()
    start_dir = tmp_path / "start"
    start_dir.mkdir()
    (tmp_path / "a.csv").write_text("a\n1")
    observed: list[Path | None] = []
    file_service = SpyFileDialogService((tmp_path / "a.csv",), observed)

    settings = SettingsService()
    settings.save_last_dataset_directory(start_dir)
    window = MainWindow(
        catalog_service=service,
        file_dialog_service=file_service,
        settings_service=settings,
    )
    qtbot.addWidget(window)

    window.desktop_actions.add_datasets.trigger()

    assert observed and observed[0] == start_dir
    assert settings.restore_last_dataset_directory() == (tmp_path / "a.csv").parent
