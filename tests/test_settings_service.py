import os
from pathlib import Path

from PyQt6.QtCore import QSettings

from wherewolf.services import SettingsService


def _configure_qsettings_path(tmp_path: Path) -> QSettings:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    settings = QSettings(SettingsService.ORGANIZATION, SettingsService.APPLICATION)
    settings.clear()
    return settings


def test_settings_service_geometry_and_state_round_trip(tmp_path: Path) -> None:
    settings = _configure_qsettings_path(tmp_path / "round_trip")
    service = SettingsService(settings)

    geometry = b"ABCD"
    state = b"EFGH"
    splitter_sizes = [120, 220]

    service.save_window_geometry(geometry)
    service.save_window_state(state)
    service.save_splitter_sizes(splitter_sizes)

    assert service.restore_window_geometry() == geometry
    assert service.restore_window_state() == state
    assert service.restore_splitter_sizes() == tuple(splitter_sizes)


def test_settings_service_returns_defaults_for_missing_keys(tmp_path: Path) -> None:
    settings = _configure_qsettings_path(tmp_path / "defaults")
    service = SettingsService(settings)

    assert service.restore_window_geometry() == b""
    assert service.restore_window_state() == b""
    assert service.restore_splitter_sizes() == service.DEFAULT_SPLITTER_SIZES
    assert service.restore_editor_font_size() == service.DEFAULT_FONT_SIZE


def test_settings_service_corrupt_value_falls_back_for_only_that_key(tmp_path: Path) -> None:
    settings = _configure_qsettings_path(tmp_path / "corrupt")
    service = SettingsService(settings)

    service.save_window_state(b"valid-state")
    service._settings.setValue(service.window_geometry_key, "garbage")

    assert service.restore_window_geometry() == b""
    assert service.restore_window_state() == b"valid-state"


def test_settings_service_namespaces_keys_with_schema_version(tmp_path: Path) -> None:
    settings = _configure_qsettings_path(tmp_path / "namespaced")
    service = SettingsService(settings)

    assert service.namespace_prefix == "v1"
    assert service.window_geometry_key.startswith("v1/")
    assert service.window_state_key.startswith("v1/")
    assert service.splitter_sizes_key.startswith("v1/")
    assert service.editor_font_size_key.startswith("v1/")
