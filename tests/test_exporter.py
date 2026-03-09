import pytest
import pandas as pd
import io
from wherewolf.export import Exporter


@pytest.fixture
def sample_df():
    return pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})


def test_export_csv(sample_df):
    csv_bytes = Exporter.to_csv(sample_df)
    assert isinstance(csv_bytes, bytes)
    df_read = pd.read_csv(io.BytesIO(csv_bytes))
    pd.testing.assert_frame_equal(sample_df, df_read)


def test_export_excel(sample_df):
    excel_bytes = Exporter.to_excel(sample_df)
    assert isinstance(excel_bytes, bytes)
    df_read = pd.read_excel(io.BytesIO(excel_bytes), engine="openpyxl")
    pd.testing.assert_frame_equal(sample_df, df_read)


def test_export_parquet(sample_df):
    parquet_bytes = Exporter.to_parquet(sample_df)
    assert isinstance(parquet_bytes, bytes)
    df_read = pd.read_parquet(io.BytesIO(parquet_bytes))
    pd.testing.assert_frame_equal(sample_df, df_read)
