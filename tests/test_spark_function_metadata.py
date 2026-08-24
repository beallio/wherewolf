from dataclasses import FrozenInstanceError, dataclass

import pytest

from wherewolf.services.spark_function_metadata import (
    current_spark_function_metadata,
    load_spark_function_metadata,
    normalize_spark_functions,
    reset_spark_function_metadata_for_tests,
)
from wherewolf.services.sql_metadata import FunctionContext


@dataclass(frozen=True)
class FakeFunction:
    name: str
    description: str | None = None


def test_normalize_spark_functions_filters_and_classifies_catalog_records() -> None:
    metadata = normalize_spark_functions(
        (
            FakeFunction("url_decode", "URL_DECODE(str) - decodes a URL"),
            FakeFunction("range", "RANGE(end) - table-valued range"),
            FakeFunction("explode", "EXPLODE(expr) - generator"),
            FakeFunction("CASE", "CASE WHEN condition THEN value END"),
            FakeFunction("+", "+(left, right)"),
            FakeFunction("missing_description"),
        ),
        table_function_names=frozenset({"range", "explode"}),
    )
    functions = {function.name: function for function in metadata.all_functions}

    assert set(functions) >= {"URL_DECODE", "RANGE", "EXPLODE", "MISSING_DESCRIPTION"}
    assert "CASE" not in functions
    assert "+" not in functions
    assert functions["EXPLODE"].signature == "EXPLODE(expr)"
    assert functions["MISSING_DESCRIPTION"].signature == "MISSING_DESCRIPTION(...)"
    assert FunctionContext.EXPRESSION in functions["EXPLODE"].contexts
    assert FunctionContext.TABLE in functions["EXPLODE"].contexts
    assert functions["RANGE"].contexts == frozenset({FunctionContext.TABLE})
    assert metadata.all_functions == tuple(
        sorted(
            metadata.all_functions, key=lambda function: (function.name.casefold(), function.name)
        )
    )
    attribute_name = "expression"
    with pytest.raises(FrozenInstanceError):
        setattr(metadata, attribute_name, ())


def test_spark_metadata_loader_uses_one_child_session_and_caches_result() -> None:
    class FakeCatalog:
        def __init__(self) -> None:
            self.calls = 0

        def listFunctions(self) -> tuple[FakeFunction, ...]:
            self.calls += 1
            return (FakeFunction("url_decode", "URL_DECODE(value)"),)

    class FakeChildSession:
        def __init__(self) -> None:
            self.catalog = FakeCatalog()

    child = FakeChildSession()
    session_factory_calls = 0

    def child_session_factory() -> FakeChildSession:
        nonlocal session_factory_calls
        session_factory_calls += 1
        return child

    reset_spark_function_metadata_for_tests()
    try:
        first = load_spark_function_metadata(
            session_factory=child_session_factory,
            table_function_names=frozenset(),
        )
        second = load_spark_function_metadata(
            session_factory=child_session_factory,
            table_function_names=frozenset(),
        )
    finally:
        reset_spark_function_metadata_for_tests()

    assert first is second
    assert session_factory_calls == 1
    assert child.catalog.calls == 1
    assert "URL_DECODE" in {function.name for function in first.all_functions}
    assert "ROOT_ONLY_UDF" not in {function.name for function in first.all_functions}


def test_spark_metadata_loader_falls_back_without_pyspark_or_catalog_errors() -> None:
    def unavailable_session() -> object:
        raise RuntimeError("PySpark is unavailable")

    reset_spark_function_metadata_for_tests()
    try:
        fallback = load_spark_function_metadata(session_factory=unavailable_session)
        current = current_spark_function_metadata()
    finally:
        reset_spark_function_metadata_for_tests()

    assert fallback is current
    assert "EXPLODE" in {function.name for function in fallback.all_functions}


@pytest.mark.spark
def test_live_spark_metadata_catalog_has_safe_dynamic_functions() -> None:
    reset_spark_function_metadata_for_tests()
    try:
        metadata = load_spark_function_metadata()
    finally:
        reset_spark_function_metadata_for_tests()

    functions = {function.name: function for function in metadata.all_functions}
    assert len(functions) > 500
    assert "URL_DECODE" in functions
    assert "RANGE" in functions
    assert "EXPLODE" in functions
    assert "CASE" not in functions
    assert all(
        function.signature and len(function.signature) <= 96 for function in functions.values()
    )
    assert FunctionContext.TABLE in functions["RANGE"].contexts
    assert functions["EXPLODE"].contexts == frozenset(
        {FunctionContext.EXPRESSION, FunctionContext.TABLE}
    )


@pytest.mark.spark
def test_spark_metadata_and_query_use_isolated_sessions_from_one_root() -> None:
    from concurrent.futures import ThreadPoolExecutor

    from wherewolf.execution.spark_engine import SparkEngine
    from wherewolf.execution.spark_runtime import reset_spark_runtime_for_tests

    reset_spark_runtime_for_tests()
    reset_spark_function_metadata_for_tests()
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            metadata_future = executor.submit(load_spark_function_metadata)
            query_future = executor.submit(SparkEngine().execute, "SELECT 1", "", 1)
            metadata = metadata_future.result()
            query = query_future.result()
    finally:
        reset_spark_function_metadata_for_tests()
        reset_spark_runtime_for_tests()

    assert query.success is True
    assert "URL_DECODE" in {function.name for function in metadata.all_functions}
