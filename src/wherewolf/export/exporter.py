import pandas as pd
import io


class Exporter:
    """Utility to convert DataFrames to various byte formats for download."""

    @staticmethod
    def to_csv(df: pd.DataFrame) -> bytes:
        """Converts DataFrame to CSV bytes."""
        return df.to_csv(index=False).encode("utf-8")

    @staticmethod
    def to_excel(df: pd.DataFrame) -> bytes:
        """Converts DataFrame to Excel bytes."""
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()

    @staticmethod
    def to_parquet(df: pd.DataFrame) -> bytes:
        """Converts DataFrame to Parquet bytes."""
        output = io.BytesIO()
        df.to_parquet(output, index=False)
        return output.getvalue()
