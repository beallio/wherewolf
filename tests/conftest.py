import os
from collections.abc import Iterator
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtCore import QSettings

from wherewolf.services import SettingsService
from wherewolf.storage import HistoryManager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def spark_session() -> Iterator[Any]:
    """Provide one explicitly bounded local Spark session for the Spark tier."""
    if find_spec("pyspark") is None:
        pytest.skip("PySpark is not installed; install the spark extra")

    spark_local_dir = Path("/tmp/wherewolf/spark-local")
    spark_local_dir.mkdir(parents=True, exist_ok=True)
    os.environ["SPARK_LOCAL_DIRS"] = str(spark_local_dir)

    try:
        from pyspark.sql import SparkSession

        session = (
            SparkSession.builder.appName("wherewolf-tests")
            .master("local[1]")
            .config("spark.driver.memory", "512m")
            .config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "1")
            .getOrCreate()
        )
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"Spark session cannot start; check Java and the spark extra: {error}")

    try:
        yield session
    finally:
        session.stop()


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
