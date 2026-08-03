from wherewolf.constants import DIALECT_MAPPING, SUPPORTED_EXTENSIONS
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
    assert {"Oracle", "PostgreSQL"} <= DIALECT_MAPPING.keys()
    for value in DIALECT_MAPPING.values():
        assert value in Translator.VALID_DIALECTS
