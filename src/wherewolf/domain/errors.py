class WherewolfError(Exception):
    """Base error for domain-level failures."""


class UnsupportedFormatError(WherewolfError, ValueError):
    """Raised when a user-provides path cannot be mapped to a source format."""


class EngineUnavailableError(WherewolfError, RuntimeError):
    """Raised when a requested execution engine is unavailable."""


class TranslationError(WherewolfError, ValueError):
    """Raised when SQL translation fails."""
