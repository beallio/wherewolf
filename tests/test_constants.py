from wherewolf import constants
from wherewolf.constants import DIALECT_MAPPING
from wherewolf.translation import Translator


def test_supported_extensions_is_not_exported():
    assert not hasattr(constants, "SUPPORTED_EXTENSIONS")


def test_dialect_mapping():
    assert {"Oracle", "PostgreSQL"} <= DIALECT_MAPPING.keys()
    for value in DIALECT_MAPPING.values():
        assert value in Translator.VALID_DIALECTS
