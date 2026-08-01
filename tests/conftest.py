import os
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings

from wherewolf.services import SettingsService
from wherewolf.storage import HistoryManager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

APPTEST_TIMEOUT = 30


@pytest.fixture(autouse=True)
def isolate_persistent_desktop_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep default desktop persistence away from each developer's real profile."""
    monkeypatch.setattr(HistoryManager, "DEFAULT_PATH", tmp_path / "history" / "history.json")

    settings_path = tmp_path / "qsettings"
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_path))
    QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, str(settings_path))
    settings = QSettings(SettingsService.ORGANIZATION, SettingsService.APPLICATION)
    settings.clear()


def pytest_sessionstart(session):
    cov_plugin = session.config.pluginmanager.get_plugin("_cov")
    if cov_plugin and hasattr(cov_plugin, "cov_controller") and cov_plugin.cov_controller:
        cov = cov_plugin.cov_controller.cov
        if cov and hasattr(cov, "config"):
            print(f"\n[PYTEST-COV] ACTIVE COVERAGE TIMID = {cov.config.timid}", flush=True)
