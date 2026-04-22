import pandas as pd
from wherewolf.execution import DuckDBEngine, SparkEngine


def test_duckdb_multi_dataset_join(tmp_path):
    """Verify DuckDB can register and join multiple datasets."""
    path1 = tmp_path / "users.csv"
    path2 = tmp_path / "orders.parquet"

    pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}).to_csv(path1, index=False)
    pd.DataFrame({"user_id": [1, 2], "amount": [100, 200]}).to_parquet(path2, index=False)

    engine = DuckDBEngine()
    catalog = {"u": str(path1), "o": str(path2)}

    # The new execute signature should take catalog instead of path
    query = "SELECT u.name, o.amount FROM u JOIN o ON u.id = o.user_id"
    result = engine.execute(query, catalog=catalog)

    assert result.success, f"Query failed: {result.error_message}"
    assert len(result.df) == 2
    assert list(result.df.columns) == ["name", "amount"]


def test_spark_multi_dataset_join(tmp_path):
    """Verify Spark can register and join multiple datasets."""
    path1 = tmp_path / "users.csv"
    path2 = tmp_path / "orders.parquet"

    pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]}).to_csv(path1, index=False)
    pd.DataFrame({"user_id": [1, 2], "amount": [100, 200]}).to_parquet(path2, index=False)

    engine = SparkEngine()
    catalog = {"u": str(path1), "o": str(path2)}

    query = "SELECT u.name, o.amount FROM u JOIN o ON u.id = o.user_id"
    result = engine.execute(query, catalog=catalog)

    assert result.success, f"Query failed: {result.error_message}"
    assert len(result.df) == 2
    assert list(result.df.columns) == ["name", "amount"]
