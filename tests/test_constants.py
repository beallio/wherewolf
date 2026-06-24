from wherewolf.constants import SUPPORTED_EXTENSIONS, DIALECT_MAPPING
from wherewolf.translation import Translator


def test_supported_extensions():
    """Verify supported extensions are correctly defined."""
    assert ".csv" in SUPPORTED_EXTENSIONS
    assert ".parquet" in SUPPORTED_EXTENSIONS
    assert ".json" in SUPPORTED_EXTENSIONS
    assert ".xlsx" in SUPPORTED_EXTENSIONS
    assert ".xls" in SUPPORTED_EXTENSIONS
    assert len(SUPPORTED_EXTENSIONS) == 5


def test_dialect_mapping():
    assert DIALECT_MAPPING == {"DuckDB": "duckdb", "Spark": "spark", "Azure SQL": "tsql"}
    for value in DIALECT_MAPPING.values():
        assert value in Translator.VALID_DIALECTS
