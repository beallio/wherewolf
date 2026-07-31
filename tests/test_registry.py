import subprocess
import sys
from uuid import uuid4

import pytest

from wherewolf.domain import (
    EngineKind,
)
from wherewolf.domain.errors import EngineUnavailableError
from wherewolf.execution.base import ExecutionEngine
from wherewolf.execution.registry import EngineRegistry


def test_registry_always_includes_duckdb() -> None:
    reg = EngineRegistry()
    available = reg.available_engines()

    assert any(descriptor.kind == EngineKind.DUCKDB for descriptor in available)


def test_spark_descriptor_reflects_find_spec(monkeypatch) -> None:
    reg = EngineRegistry()

    spark_present = next(
        descriptor for descriptor in reg.available_engines() if descriptor.kind == EngineKind.SPARK
    )
    assert spark_present.available is (
        None is not __import__("importlib.util").util.find_spec("pyspark")
    )

    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    spark_absent = next(
        descriptor for descriptor in reg.available_engines() if descriptor.kind == EngineKind.SPARK
    )
    assert spark_absent.available is False
    assert spark_absent.unavailable_reason is not None
    assert "pyspark" in spark_absent.unavailable_reason.lower()


def test_registry_available_engines_does_not_import_pyspark_subprocess() -> None:
    code = (
        "import sys\n"
        "import wherewolf.execution.registry as r\n"
        "r.EngineRegistry().available_engines()\n"
        "import sys\n"
        "if 'pyspark' in sys.modules:\n"
        "    raise SystemExit('pyspark unexpectedly imported')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_registry_create_returns_execution_engine() -> None:
    reg = EngineRegistry()
    engine = reg.create(EngineKind.DUCKDB, uuid4())

    assert isinstance(engine, ExecutionEngine)


def test_registry_create_spark_unavailable_raises(monkeypatch) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    reg = EngineRegistry()

    with pytest.raises(EngineUnavailableError):
        reg.create(EngineKind.SPARK, uuid4())


def test_registry_create_duckdb_returns_request_scoped_instances() -> None:
    reg = EngineRegistry()
    first = reg.create(EngineKind.DUCKDB, uuid4())
    second = reg.create(EngineKind.DUCKDB, uuid4())
    assert first is not second
