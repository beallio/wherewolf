import pytest

from wherewolf.services.sql_metadata import (
    SqlFunctionInfo,
    get_dialect_functions,
    get_dialect_keywords,
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
