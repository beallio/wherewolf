import os
from pathlib import Path

import pytest
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


def test_settings_service_window_layout_version_round_trip(tmp_path: Path) -> None:
    service = SettingsService(_configure_qsettings_path(tmp_path / "layout-version"))

    assert service.restore_window_layout_version() == service.DEFAULT_LAYOUT_VERSION
    service.save_window_layout_version(2)

    assert service.restore_window_layout_version() == 2


def test_settings_service_program_theme_round_trip(tmp_path: Path) -> None:
    service = SettingsService(_configure_qsettings_path(tmp_path / "program-theme"))

    assert service.restore_program_theme() == service.DEFAULT_PROGRAM_THEME
    service.save_program_theme("Dark")

    assert service.restore_program_theme() == "Dark"


def test_settings_service_returns_defaults_for_missing_keys(tmp_path: Path) -> None:
    settings = _configure_qsettings_path(tmp_path / "defaults")
    service = SettingsService(settings)

    assert service.restore_window_geometry() == b""
    assert service.restore_window_state() == b""
    assert service.restore_splitter_sizes() == service.DEFAULT_SPLITTER_SIZES
    assert service.restore_editor_font_size() == service.DEFAULT_FONT_SIZE
    assert service.restore_preview_limit() == 1000
    assert isinstance(service.restore_last_dataset_directory(), Path)


def test_settings_service_corrupt_value_falls_back_for_only_that_key(tmp_path: Path) -> None:
    settings = _configure_qsettings_path(tmp_path / "corrupt")
    service = SettingsService(settings)

    service.save_window_state(b"valid-state")
    service.save_last_dataset_directory(Path("/tmp/expected"))
    service._settings.setValue(service.window_geometry_key, "garbage")

    assert service.restore_window_geometry() == b""
    assert service.restore_window_state() == b"valid-state"
    assert service.restore_last_dataset_directory() == Path("/tmp/expected")


def test_settings_service_namespaces_keys_with_schema_version(tmp_path: Path) -> None:
    settings = _configure_qsettings_path(tmp_path / "namespaced")
    service = SettingsService(settings)

    assert service.namespace_prefix == "v1"
    assert service.window_geometry_key.startswith("v1/")
    assert service.window_state_key.startswith("v1/")
    assert service.splitter_sizes_key.startswith("v1/")
    assert service.editor_font_size_key.startswith("v1/")
    assert service.last_dataset_directory_key.startswith("v1/")


def test_settings_service_last_dataset_directory_round_trip(tmp_path: Path) -> None:
    settings = _configure_qsettings_path(tmp_path / "dataset_dir")
    service = SettingsService(settings)

    expected = Path(tmp_path / "dataset")
    service.save_last_dataset_directory(expected)

    assert service.restore_last_dataset_directory() == expected


def test_settings_service_last_dataset_directory_falls_back_for_corrupt(tmp_path: Path) -> None:
    settings = _configure_qsettings_path(tmp_path / "dataset_corrupt")
    service = SettingsService(settings)

    service.save_last_dataset_directory(Path("/tmp/valid"))
    service._settings.setValue(service.last_dataset_directory_key, 1234)

    assert service.restore_last_dataset_directory() == service.DEFAULT_DATASET_DIRECTORY


def test_settings_service_completion_threshold_and_enabled_round_trip(tmp_path: Path) -> None:
    settings = _configure_qsettings_path(tmp_path / "completion")
    service = SettingsService(settings)

    assert service.restore_completion_threshold() == 2
    assert service.restore_completion_enabled() is True

    service.save_completion_threshold(3)
    service.save_completion_enabled(False)

    assert service.restore_completion_threshold() == 3
    assert service.restore_completion_enabled() is False


def test_settings_service_preview_limit_and_editor_theme_round_trip(tmp_path: Path) -> None:
    service = SettingsService(_configure_qsettings_path(tmp_path / "editor-preferences"))

    service.save_preview_limit(250)
    service.save_editor_theme("Light")

    assert service.restore_preview_limit() == 250
    assert service.restore_editor_theme() == "Light"


def test_settings_service_result_column_auto_size_preferences_round_trip_and_validate_width(
    tmp_path: Path,
) -> None:
    service = SettingsService(_configure_qsettings_path(tmp_path / "result-column-auto-size"))

    assert service.restore_auto_size_columns() is True
    assert service.restore_auto_size_max_width() == 300

    service.save_auto_size_columns(False)
    service.save_auto_size_max_width(450)

    assert service.restore_auto_size_columns() is False
    assert service.restore_auto_size_max_width() == 450

    service.save_auto_size_max_width(5)
    assert service.restore_auto_size_max_width() == 50
    service.save_auto_size_max_width(9999)
    assert service.restore_auto_size_max_width() == 2000

    for invalid_width in (5, 9999, True):
        service._settings.setValue(service.auto_size_max_width_key, invalid_width)
        assert service.restore_auto_size_max_width() == 300


def test_settings_service_export_preferences_round_trip(tmp_path: Path) -> None:
    service = SettingsService(_configure_qsettings_path(tmp_path / "export-preferences"))

    assert service.restore_export_format() == "csv"
    assert service.restore_export_scope() == "preview"
    service.save_export_format("parquet")
    service.save_export_scope("selection")

    assert service.restore_export_format() == "parquet"
    assert service.restore_export_scope() == "selection"


def test_profile_preferences_default_on_and_round_trip(tmp_path: Path) -> None:
    service = SettingsService(_configure_qsettings_path(tmp_path / "profile"))

    assert service.restore_profile_on_load() is True
    assert service.restore_profile_max_bytes() == 268_435_456
    service.save_profile_on_load(False)
    service.save_profile_max_bytes(12)
    assert service.restore_profile_on_load() is False
    assert service.restore_profile_max_bytes() == 12


def test_settings_service_round_trips_every_persistent_setting(tmp_path: Path) -> None:
    service = SettingsService(_configure_qsettings_path(tmp_path / "all-round-trips"))

    service.save_window_geometry(b"geometry")
    service.save_window_state(b"window-state")
    service.save_splitter_sizes((240, 360))
    service.save_editor_font_size(15)
    service.save_last_dataset_directory(Path("/tmp/wherewolf-dataset"))
    service.save_completion_threshold(4)
    service.save_completion_enabled(False)

    assert service.restore_window_geometry() == b"geometry"
    assert service.restore_window_state() == b"window-state"
    assert service.restore_splitter_sizes() == (240, 360)
    assert service.restore_editor_font_size() == 15
    assert service.restore_last_dataset_directory() == Path("/tmp/wherewolf-dataset")
    assert service.restore_completion_threshold() == 4
    assert service.restore_completion_enabled() is False


@pytest.mark.parametrize(
    ("key_name", "corrupt_value", "restore_name", "expected_default"),
    [
        ("window_geometry_key", "not-bytes", "restore_window_geometry", b""),
        ("window_state_key", ["not", "bytes"], "restore_window_state", b""),
        ("splitter_sizes_key", ["not", "sizes"], "restore_splitter_sizes", (1, 1)),
        ("editor_font_size_key", "twelve", "restore_editor_font_size", 12),
        (
            "last_dataset_directory_key",
            42,
            "restore_last_dataset_directory",
            SettingsService.DEFAULT_DATASET_DIRECTORY,
        ),
        ("completion_threshold_key", True, "restore_completion_threshold", 2),
        ("completion_enabled_key", "false", "restore_completion_enabled", True),
    ],
)
def test_settings_service_each_corrupt_value_falls_back_to_its_default(
    tmp_path: Path,
    key_name: str,
    corrupt_value: object,
    restore_name: str,
    expected_default: object,
) -> None:
    service = SettingsService(_configure_qsettings_path(tmp_path / key_name))
    service._settings.setValue(getattr(service, key_name), corrupt_value)

    restored = getattr(service, restore_name)()

    assert restored == expected_default


def test_settings_service_saved_query_directory_round_trip(tmp_path: Path) -> None:
    service = SettingsService(_configure_qsettings_path(tmp_path / "saved-query-directory"))

    assert service.restore_saved_query_directory() == service.DEFAULT_SAVED_QUERY_DIRECTORY

    chosen = tmp_path / "library"
    service.save_saved_query_directory(chosen)

    assert service.restore_saved_query_directory() == chosen
    assert service.saved_query_directory_key.endswith("/saved_queries/directory")


def test_settings_service_blank_saved_query_directory_falls_back_to_the_default(
    tmp_path: Path,
) -> None:
    service = SettingsService(_configure_qsettings_path(tmp_path / "blank-directory"))
    service._settings.setValue(service.saved_query_directory_key, "")

    assert service.restore_saved_query_directory() == service.DEFAULT_SAVED_QUERY_DIRECTORY
