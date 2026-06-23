from wherewolf.execution.models import QueryResult
import polars as pl


def test_models():
    qr = QueryResult()
    assert qr.success is True
    assert isinstance(qr.df, pl.DataFrame)
