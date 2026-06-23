import polars as pl
import io


class Exporter:
    """Utility to convert DataFrames to various byte formats for download."""

    @staticmethod
    def to_csv(df: pl.DataFrame) -> bytes:
        """Converts DataFrame to CSV bytes."""
        return df.write_csv().encode("utf-8")

    @staticmethod
    def to_excel(df: pl.DataFrame) -> bytes:
        """Converts DataFrame to Excel bytes."""
        output = io.BytesIO()
        df.write_excel(output)
        return output.getvalue()

    @staticmethod
    def to_parquet(df: pl.DataFrame) -> bytes:
        """Converts DataFrame to Parquet bytes."""
        output = io.BytesIO()
        df.write_parquet(output)
        return output.getvalue()
