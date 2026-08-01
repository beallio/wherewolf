"""Service-layer entrypoints for desktop settings persistence."""

from .catalog_service import CatalogService, CatalogServiceReport
from .completion_service import SqlCompletionService
from .formatting_service import FormattingResult, SqlFormattingService
from .settings_service import SettingsService
from .statement_service import StatementSelection, StatementService, StatementSpan

__all__ = [
    "CatalogService",
    "CatalogServiceReport",
    "FormattingResult",
    "SettingsService",
    "SqlCompletionService",
    "SqlFormattingService",
    "StatementSelection",
    "StatementService",
    "StatementSpan",
]
