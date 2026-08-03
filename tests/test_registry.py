import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import polars as pl
import pytest

from wherewolf.domain import (
    CatalogEntry,
    EngineKind,
    SourceFormat,
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
    assert "wherewolf[spark]" in spark_absent.unavailable_reason


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


def test_duckdb_adapter_profiles_mixed_columns_from_a_fixture_file(tmp_path: Path) -> None:
    fixture = tmp_path / "mixed.csv"
    fixture.write_text(
        "integer_value,float_value,category,nullable_value\n"
        "1,1.5,alpha,10\n"
        "2,2.5,beta,\n"
        "3,,alpha,30\n"
    )
    entry = CatalogEntry(id=uuid4(), alias="mixed", path=fixture, source_format=SourceFormat.CSV)

    result = EngineRegistry().create(EngineKind.DUCKDB, uuid4()).profile_dataset(entry)

    assert result.error_message is None
    assert result.profiles is not None
    profiles = {profile.name: profile for profile in result.profiles}
    assert profiles["nullable_value"].null_percentage == pytest.approx(33.33, abs=0.01)
    assert profiles["category"].avg is None
    assert profiles["category"].std is None
    assert profiles["category"].q25 is None
    assert profiles["category"].q50 is None
    assert profiles["category"].q75 is None


def test_spark_adapter_reports_that_profiling_is_unsupported(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(EngineRegistry, "_is_spark_available", lambda self: True)
    entry = CatalogEntry(
        id=uuid4(),
        alias="events",
        path=tmp_path / "events.csv",
        source_format=SourceFormat.CSV,
    )

    result = EngineRegistry().create(EngineKind.SPARK, uuid4()).profile_dataset(entry)

    assert result.profiles == ()
    assert result.error_message is not None
    assert "profiling is not available for this engine" in result.error_message.lower()


def test_spark_schema_failure_is_distinguishable_from_an_empty_schema(
    monkeypatch, tmp_path
) -> None:
    from wherewolf.domain import CatalogEntry, SourceFormat
    from wherewolf.execution.spark_engine import SparkEngine

    monkeypatch.setattr(EngineRegistry, "_is_spark_available", lambda self: True)
    entry = CatalogEntry(
        id=uuid4(),
        alias="events",
        path=tmp_path / "events.csv",
        source_format=SourceFormat.CSV,
    )
    adapter = EngineRegistry().create(EngineKind.SPARK, uuid4())

    monkeypatch.setattr(
        SparkEngine,
        "get_schema",
        lambda self, path: (_ for _ in ()).throw(OSError("unreadable")),
    )
    failed = adapter.inspect_schema(entry)

    monkeypatch.setattr(
        SparkEngine,
        "get_schema",
        lambda self, path: pl.DataFrame(schema={"Column": pl.Utf8, "Type": pl.Utf8}),
    )
    empty = adapter.inspect_schema(entry)

    assert failed.columns == ()
    assert failed.error_type == "OSError"
    assert failed.error_message == "unreadable"
    assert empty.columns == ()
    assert empty.error_type is None
    assert empty.error_message is None


def test_registry_create_duckdb_returns_request_scoped_instances() -> None:
    reg = EngineRegistry()
    first = reg.create(EngineKind.DUCKDB, uuid4())
    second = reg.create(EngineKind.DUCKDB, uuid4())
    assert first is not second


def test_duckdb_adapter_fresh_connection_per_request(tmp_path: Path) -> None:
    csv_file = tmp_path / "events.csv"
    csv_file.write_text("id,val\n1,100\n2,200\n")

    from wherewolf.services.catalog_service import CatalogService
    from wherewolf.services.execution_request_builder import ExecutionRequestBuilder

    reg = EngineRegistry()

    req_id1 = uuid4()
    adapter1 = reg.create(EngineKind.DUCKDB, req_id1)

    catalog_service1 = CatalogService()
    catalog_service1.add_paths((csv_file,))
    req1 = ExecutionRequestBuilder.build(
        sql="SELECT * FROM events",
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=catalog_service1,
    )

    res1 = adapter1.execute_preview(req1)
    assert res1.status.name == "SUCCEEDED"
    assert res1.frame is not None
    assert res1.frame.height == 2

    # Request 2 omits the catalog binding; duckdb connection must be fresh and not retain 'events'
    req_id2 = uuid4()
    adapter2 = reg.create(EngineKind.DUCKDB, req_id2)
    empty_catalog_service = CatalogService()
    req2 = ExecutionRequestBuilder.build(
        sql="SELECT * FROM events",
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=empty_catalog_service,
    )

    res2 = adapter2.execute_preview(req2)
    assert res2.status.name == "FAILED"
    assert res2.frame is None
    assert res2.error_message is not None
    assert (
        "events" in res2.error_message.lower()
        or "catalog" in res2.error_message.lower()
        or "table" in res2.error_message.lower()
    )


def test_duckdb_adapter_truncation_limit_plus_one(tmp_path: Path) -> None:
    csv_file = tmp_path / "rows.csv"
    csv_file.write_text("id\n1\n2\n3\n4\n5\n")

    from wherewolf.services.catalog_service import CatalogService
    from wherewolf.services.execution_request_builder import ExecutionRequestBuilder

    cs = CatalogService()
    cs.add_paths((csv_file,))

    reg = EngineRegistry()
    adapter = reg.create(EngineKind.DUCKDB, uuid4())

    # Limit 2 over 5 rows -> preview_row_count 2, truncated True, total_row_count None
    req_truncated = ExecutionRequestBuilder.build(
        sql="SELECT * FROM rows",
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=cs,
        preview_limit=2,
    )
    res_truncated = adapter.execute_preview(req_truncated)
    assert res_truncated.status.name == "SUCCEEDED"
    assert res_truncated.preview_row_count == 2
    assert res_truncated.total_row_count is None
    assert res_truncated.truncated is True
    assert res_truncated.frame is not None and res_truncated.frame.height == 2

    # Limit 5 over 5 rows -> preview_row_count 5, truncated False, total_row_count None
    req_exact = ExecutionRequestBuilder.build(
        sql="SELECT * FROM rows",
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=cs,
        preview_limit=5,
    )
    res_exact = adapter.execute_preview(req_exact)
    assert res_exact.status.name == "SUCCEEDED"
    assert res_exact.preview_row_count == 5
    assert res_exact.total_row_count is None
    assert res_exact.truncated is False
    assert res_exact.frame is not None and res_exact.frame.height == 5


def test_duckdb_adapter_sql_error_handling() -> None:
    from wherewolf.services.catalog_service import CatalogService
    from wherewolf.services.execution_request_builder import ExecutionRequestBuilder

    cs = CatalogService()
    reg = EngineRegistry()
    adapter = reg.create(EngineKind.DUCKDB, uuid4())

    req = ExecutionRequestBuilder.build(
        sql="SELECT * FROM non_existent_table_9999",
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=cs,
    )
    res = adapter.execute_preview(req)
    assert res.status.name == "FAILED"
    assert res.frame is None
    assert res.error_type is not None
    assert res.error_message is not None


def test_duckdb_adapter_cancellation_handle_matches_request_id() -> None:
    req_id = uuid4()
    reg = EngineRegistry()
    adapter = reg.create(EngineKind.DUCKDB, req_id)
    handle = adapter.cancellation_handle()

    assert handle.request_id == req_id


def test_duckdb_adapter_cancel_inactive_or_finished_is_safe() -> None:
    req_id = uuid4()
    reg = EngineRegistry()
    adapter = reg.create(EngineKind.DUCKDB, req_id)
    handle = adapter.cancellation_handle()

    # Safe to call cancel when no query is running
    assert handle.cancel() is True


def test_duckdb_adapter_cancellation_yields_cancelled_status(tmp_path: Path) -> None:
    csv_file = tmp_path / "big.csv"
    # Generate enough rows so query takes time, or interrupt during query
    csv_file.write_text("id\n" + "\n".join(str(i) for i in range(100_000)) + "\n")

    from wherewolf.domain import ExecutionStatus
    from wherewolf.services.catalog_service import CatalogService
    from wherewolf.services.execution_request_builder import ExecutionRequestBuilder

    cs = CatalogService()
    cs.add_paths((csv_file,))

    req_id = uuid4()
    reg = EngineRegistry()
    adapter = reg.create(EngineKind.DUCKDB, req_id)
    handle = adapter.cancellation_handle()

    # Pre-interrupt or interrupt during run via handle
    handle.cancel()

    req = ExecutionRequestBuilder.build(
        sql="SELECT id, count(*) FROM big GROUP BY id ORDER BY id DESC",
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=cs,
    )

    res = adapter.execute_preview(req)
    assert res.status is ExecutionStatus.CANCELLED
    assert res.frame is None


def test_duckdb_adapter_cancel_one_adapter_does_not_affect_another(tmp_path: Path) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("id\n1\n2\n")

    from wherewolf.domain import ExecutionStatus
    from wherewolf.services.catalog_service import CatalogService
    from wherewolf.services.execution_request_builder import ExecutionRequestBuilder

    cs = CatalogService()
    cs.add_paths((csv_file,))

    reg = EngineRegistry()
    adapter1 = reg.create(EngineKind.DUCKDB, uuid4())
    adapter2 = reg.create(EngineKind.DUCKDB, uuid4())

    handle1 = adapter1.cancellation_handle()
    handle1.cancel()

    req = ExecutionRequestBuilder.build(
        sql="SELECT * FROM data",
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=cs,
    )

    res1 = adapter1.execute_preview(req)
    res2 = adapter2.execute_preview(req)

    assert res1.status is ExecutionStatus.CANCELLED
    assert res2.status is ExecutionStatus.SUCCEEDED


def test_duckdb_adapter_closes_connection(tmp_path: Path, monkeypatch) -> None:
    import duckdb

    from wherewolf.services.catalog_service import CatalogService
    from wherewolf.services.execution_request_builder import ExecutionRequestBuilder

    cs = CatalogService()
    reg = EngineRegistry()
    adapter = reg.create(EngineKind.DUCKDB, uuid4())

    real_connect = duckdb.connect
    closed = False

    class _ConWrapper:
        def __init__(self, con):
            self._con = con

        def __getattr__(self, item):
            return getattr(self._con, item)

        def close(self):
            nonlocal closed
            closed = True
            return self._con.close()

    monkeypatch.setattr("duckdb.connect", lambda **kwargs: _ConWrapper(real_connect(**kwargs)))

    req = ExecutionRequestBuilder.build(
        sql="SELECT 1",
        source_dialect="duckdb",
        engine=EngineKind.DUCKDB,
        catalog_service=cs,
    )
    adapter.execute_preview(req)
    assert closed is True


@pytest.mark.parametrize(
    ("pyspark", "java", "available", "reason"),
    [
        (False, False, False, "pyspark and Java"),
        (False, True, False, "pyspark"),
        (True, False, False, "Java"),
        (True, True, True, None),
    ],
)
def test_spark_availability_requires_pyspark_and_java(
    monkeypatch, pyspark: bool, java: bool, available: bool, reason: str | None
) -> None:
    registry = EngineRegistry()
    monkeypatch.setattr(registry, "_pyspark_available", lambda: pyspark)
    monkeypatch.setattr(registry, "_java_available", lambda: java)

    descriptor = registry._spark_descriptor()

    assert descriptor.available is available
    if reason is not None:
        assert descriptor.unavailable_reason is not None
        for missing in reason.split(" and "):
            assert missing in descriptor.unavailable_reason
