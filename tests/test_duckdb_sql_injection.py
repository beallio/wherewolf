import polars as pl
from wherewolf.execution.duckdb_engine import DuckDBEngine


def test_duckdb_sql_injection_fix(tmp_path):
    # Create a file with a single quote in its name
    malicious_name = "test'quote.csv"
    p = tmp_path / malicious_name
    pl.DataFrame({"a": [1, 2, 3]}).write_csv(p)

    engine = DuckDBEngine()

    # This should now succeed
    result = engine.execute("SELECT * FROM dataset", str(p))

    assert result.success is True
    assert len(result.df) == 3
    assert result.df["a"].to_list() == [1, 2, 3]
