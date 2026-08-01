"""Desktop settings persistence for the PyQt UI shell."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Final

from PyQt6.QtCore import QByteArray, QSettings


class SettingsService:
    """Persist desktop UI state in a small, namespaced settings namespace."""

    ORGANIZATION: Final = "Wherewolf"
    APPLICATION: Final = "Wherewolf-Desktop"
    SCHEMA_VERSION: Final = "v1"
    DEFAULT_FONT_SIZE: Final = 12
    DEFAULT_SPLITTER_SIZES: Final = (1, 1)
    DEFAULT_DATASET_DIRECTORY: Final = Path.home()

    DEFAULT_COMPLETION_THRESHOLD: Final = 2
    DEFAULT_COMPLETION_ENABLED: Final = True

    def __init__(self, settings: QSettings | None = None):
        self._settings = settings or QSettings(self.ORGANIZATION, self.APPLICATION)

    @staticmethod
    def _geometry_key(schema_version: str) -> str:
        return f"{schema_version}/window/geometry"

    @staticmethod
    def _state_key(schema_version: str) -> str:
        return f"{schema_version}/window/state"

    @staticmethod
    def _splitter_key(schema_version: str) -> str:
        return f"{schema_version}/splitter/sizes"

    @staticmethod
    def _font_size_key(schema_version: str) -> str:
        return f"{schema_version}/editor/font_size"

    @staticmethod
    def _last_dataset_directory_key(schema_version: str) -> str:
        return f"{schema_version}/dataset_directory/last"

    @staticmethod
    def _completion_threshold_key(schema_version: str) -> str:
        return f"{schema_version}/completion/threshold"

    @staticmethod
    def _completion_enabled_key(schema_version: str) -> str:
        return f"{schema_version}/completion/enabled"

    @property
    def namespace_prefix(self) -> str:
        return f"{self.SCHEMA_VERSION}"

    @property
    def window_geometry_key(self) -> str:
        return self._geometry_key(self.namespace_prefix)

    @property
    def window_state_key(self) -> str:
        return self._state_key(self.namespace_prefix)

    @property
    def splitter_sizes_key(self) -> str:
        return self._splitter_key(self.namespace_prefix)

    @property
    def editor_font_size_key(self) -> str:
        return self._font_size_key(self.namespace_prefix)

    @property
    def last_dataset_directory_key(self) -> str:
        return self._last_dataset_directory_key(self.namespace_prefix)

    @property
    def completion_threshold_key(self) -> str:
        return self._completion_threshold_key(self.namespace_prefix)

    @property
    def completion_enabled_key(self) -> str:
        return self._completion_enabled_key(self.namespace_prefix)

    def restore_window_geometry(self) -> bytes:
        return self._read_bytes(self.window_geometry_key, b"")

    def save_window_geometry(self, geometry: bytes) -> None:
        self._settings.setValue(self.window_geometry_key, QByteArray(geometry))

    def restore_window_state(self) -> bytes:
        return self._read_bytes(self.window_state_key, b"")

    def save_window_state(self, state: bytes) -> None:
        self._settings.setValue(self.window_state_key, QByteArray(state))

    def restore_splitter_sizes(self) -> tuple[int, int]:
        return self._read_splitter_sizes(self.splitter_sizes_key, self.DEFAULT_SPLITTER_SIZES)

    def save_splitter_sizes(self, sizes: Iterable[int]) -> None:
        self._settings.setValue(self.splitter_sizes_key, [int(size) for size in sizes])

    def restore_editor_font_size(self) -> int:
        default = self.DEFAULT_FONT_SIZE
        value = self._settings.value(self.editor_font_size_key, default)
        if not isinstance(value, int) or isinstance(value, bool):
            return default
        return value

    def save_editor_font_size(self, size: int) -> None:
        self._settings.setValue(self.editor_font_size_key, int(size))

    def restore_last_dataset_directory(self) -> Path:
        value = self._settings.value(
            self.last_dataset_directory_key, str(self.DEFAULT_DATASET_DIRECTORY)
        )
        if not isinstance(value, str) or not value:
            return self.DEFAULT_DATASET_DIRECTORY
        return Path(value)

    def save_last_dataset_directory(self, directory: Path) -> None:
        self._settings.setValue(self.last_dataset_directory_key, str(directory))

    def restore_completion_threshold(self) -> int:
        default = self.DEFAULT_COMPLETION_THRESHOLD
        value = self._settings.value(self.completion_threshold_key, default)
        if not isinstance(value, int) or isinstance(value, bool):
            return default
        return value

    def save_completion_threshold(self, threshold: int) -> None:
        self._settings.setValue(self.completion_threshold_key, int(threshold))

    def restore_completion_enabled(self) -> bool:
        default = self.DEFAULT_COMPLETION_ENABLED
        value = self._settings.value(self.completion_enabled_key, default)
        if not isinstance(value, bool):
            return default
        return value

    def save_completion_enabled(self, enabled: bool) -> None:
        self._settings.setValue(self.completion_enabled_key, bool(enabled))

    def _read_bytes(self, key: str, default: bytes) -> bytes:
        value = self._settings.value(key, default)
        if not isinstance(value, QByteArray):
            return default
        return value.data()

    def _read_splitter_sizes(self, key: str, default: tuple[int, int]) -> tuple[int, int]:
        value = self._settings.value(key)
        if not isinstance(value, list):
            return default
        try:
            if any(isinstance(item, bool) for item in value):
                return default
            converted = tuple(int(item) for item in value)
        except (TypeError, ValueError):
            return default
        if len(converted) != 2:
            return default
        return converted
