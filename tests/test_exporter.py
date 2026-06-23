import pytest
import polars as pl
import io
from polars.testing import assert_frame_equal
from wherewolf.export import Exporter


@pytest.fixture
def sample_df():
    return pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})


def test_export_csv(sample_df):
    csv_bytes = Exporter.to_csv(sample_df)
    assert isinstance(csv_bytes, bytes)
    df_read = pl.read_csv(io.BytesIO(csv_bytes))
    assert_frame_equal(sample_df, df_read)


def test_export_excel(sample_df):
    excel_bytes = Exporter.to_excel(sample_df)
    assert isinstance(excel_bytes, bytes)
    df_read = pl.read_excel(io.BytesIO(excel_bytes))
    assert_frame_equal(sample_df, df_read)


def test_export_parquet(sample_df):
    parquet_bytes = Exporter.to_parquet(sample_df)
    assert isinstance(parquet_bytes, bytes)
    df_read = pl.read_parquet(io.BytesIO(parquet_bytes))
    assert_frame_equal(sample_df, df_read)
