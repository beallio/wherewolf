from __future__ import annotations

import importlib

from wherewolf.desktop.main_window import MainWindow
from wherewolf.domain import EngineKind
from wherewolf.execution.registry import EngineRegistry


def test_desktop_constructs_when_spark_spec_is_absent(monkeypatch, qtbot) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)

    window = MainWindow()
    qtbot.addWidget(window)
    descriptor = next(
        item for item in EngineRegistry().available_engines() if item.kind is EngineKind.SPARK
    )

    assert descriptor.available is False


def test_spark_engine_module_does_not_import_pyspark_when_spec_is_absent(monkeypatch) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    module = importlib.reload(importlib.import_module("wherewolf.execution.spark_engine"))

    assert module.SPARK_AVAILABLE is False

    monkeypatch.undo()
    importlib.reload(module)
