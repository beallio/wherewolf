import pytest

from wherewolf.services.sql_metadata import (
    SqlFunctionInfo,
    get_dialect_functions,
    get_dialect_keywords,
    get_dialect_table_functions,
    lookup_function_info,
)


def test_get_dialect_keywords() -> None:
    duck_kw = get_dialect_keywords("duckdb")
    assert len(duck_kw) > 0
    assert "SELECT" in duck_kw
    assert "QUALIFY" in duck_kw

    spark_kw = get_dialect_keywords("spark")
    assert len(spark_kw) > 0
    assert "SELECT" in spark_kw
    assert "LATERAL VIEW" in spark_kw or "LATERAL" in spark_kw

    with pytest.raises((ValueError, KeyError)):
        get_dialect_keywords("oracle_unknown")


def test_get_dialect_functions_and_call_tips() -> None:
    duck_fn = get_dialect_functions("duckdb")
    assert len(duck_fn) > 0
    names = {fn.name.upper() for fn in duck_fn}
    assert "COALESCE" in names
    assert "COUNT" in names

    spark_fn = get_dialect_functions("spark")
    assert len(spark_fn) > 0

    with pytest.raises((ValueError, KeyError)):
        get_dialect_functions("unknown_dialect")


def test_lookup_function_info_case_insensitive() -> None:
    fn1 = lookup_function_info("duckdb", "coalesce")
    assert isinstance(fn1, SqlFunctionInfo)
    assert fn1.name.upper() == "COALESCE"
    assert "(" in fn1.signature

    fn2 = lookup_function_info("duckdb", "COALESCE")
    assert fn2 == fn1

    fn_unknown = lookup_function_info("duckdb", "non_existent_fn_xyz")
    assert fn_unknown is None


def test_duckdb_metadata_includes_dynamic_expression_and_table_functions() -> None:
    expression_names = {function.name.upper() for function in get_dialect_functions("duckdb")}
    table_names = {function.name.upper() for function in get_dialect_table_functions("duckdb")}

    assert "SQRT" in expression_names
    assert "READ_CSV" in table_names
    assert "PRAGMA_SHOW" not in expression_names | table_names
    assert all(name.replace("_", "").isalnum() for name in expression_names | table_names)


def test_duckdb_metadata_is_stable_bounded_and_preserves_curated_signatures() -> None:
    first = get_dialect_functions("duckdb")
    second = get_dialect_functions("duckdb")
    read_csv = lookup_function_info("duckdb", "read_csv")
    coalesce = lookup_function_info("duckdb", "coalesce")

    assert first is second
    assert tuple(function.name for function in first) == tuple(
        sorted((function.name for function in first), key=lambda name: (name.casefold(), name))
    )
    assert read_csv is not None and 0 < len(read_csv.signature) <= 96
    assert coalesce is not None
    assert coalesce.signature == "COALESCE(val1, val2, ...)"


def test_duckdb_normalization_handles_null_metadata_and_multiple_overloads() -> None:
    from wherewolf.services import sql_metadata

    rows = (
        ("demo", "scalar", None, None, None, None),
        ("demo", "scalar", "demo description", ("value",), ("INTEGER",), None),
        ("read_demo", "table", None, tuple(f"arg_{index}" for index in range(30)), None, None),
    )

    catalog = sql_metadata._normalize_duckdb_rows(rows)
    names = {function.name: function for function in catalog.expression + catalog.table}

    assert names["DEMO"].signature.startswith("DEMO(")
    assert "+1 overload" in names["DEMO"].signature
    assert names["DEMO"].description == "demo description"
    assert 0 < len(names["READ_DEMO"].signature) <= 96


def test_duckdb_metadata_caches_success_and_curated_failure_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from wherewolf.services import sql_metadata

    class FakeCursor:
        def fetchall(self) -> tuple[tuple[object, ...], ...]:
            return (("dynamic_fn", "scalar", "dynamic", ("value",), ("INTEGER",), None),)

    class FakeConnection:
        def execute(self, query: str) -> FakeCursor:
            assert "duckdb_functions" in query
            return FakeCursor()

        def close(self) -> None:
            return None

    calls = 0

    def fake_connect(*_args: object, **_kwargs: object) -> FakeConnection:
        nonlocal calls
        calls += 1
        return FakeConnection()

    sql_metadata._load_duckdb_catalog.cache_clear()
    monkeypatch.setattr(sql_metadata.duckdb, "connect", fake_connect)
    try:
        assert "DYNAMIC_FN" in {function.name for function in get_dialect_functions("duckdb")}
        get_dialect_table_functions("duckdb")
        assert calls == 1
    finally:
        sql_metadata._load_duckdb_catalog.cache_clear()

    def raising_connect(*_args: object, **_kwargs: object) -> FakeConnection:
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(sql_metadata.duckdb, "connect", raising_connect)
    assert lookup_function_info("duckdb", "coalesce") is not None
    assert "SQRT" not in {function.name for function in get_dialect_functions("duckdb")}
    sql_metadata._load_duckdb_catalog.cache_clear()
