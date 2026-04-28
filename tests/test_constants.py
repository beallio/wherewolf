from wherewolf.constants import SUPPORTED_EXTENSIONS


def test_supported_extensions():
    """Verify supported extensions are correctly defined."""
    assert ".csv" in SUPPORTED_EXTENSIONS
    assert ".parquet" in SUPPORTED_EXTENSIONS
    assert ".json" in SUPPORTED_EXTENSIONS
    assert ".xlsx" in SUPPORTED_EXTENSIONS
    assert ".xls" in SUPPORTED_EXTENSIONS
    assert len(SUPPORTED_EXTENSIONS) == 5
