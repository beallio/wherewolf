from wherewolf.domain.errors import (
    EngineUnavailableError,
    TranslationError,
    UnsupportedFormatError,
    WherewolfError,
)


def test_domain_errors_are_subclasses_of_wherewolf_error() -> None:
    assert issubclass(EngineUnavailableError, WherewolfError)
    assert issubclass(UnsupportedFormatError, WherewolfError)
    assert issubclass(TranslationError, WherewolfError)
