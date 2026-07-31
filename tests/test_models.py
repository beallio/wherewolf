import polars as pl

from wherewolf.execution.models import QueryResult


def test_models():
    qr = QueryResult()
    assert qr.success is True
    assert isinstance(qr.df, pl.DataFrame)
