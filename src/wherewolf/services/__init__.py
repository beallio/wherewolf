"""Service-layer entrypoints for desktop settings persistence."""

from .catalog_service import CatalogService, CatalogServiceReport
from .completion_service import SqlCompletionService
from .execution_request_builder import ExecutionRequestBuilder
from .formatting_service import FormattingResult, SqlFormattingService
from .settings_service import SettingsService
from .statement_service import StatementSelection, StatementService, StatementSpan

__all__ = [
    "CatalogService",
    "CatalogServiceReport",
    "ExecutionRequestBuilder",
    "FormattingResult",
    "SettingsService",
    "SqlCompletionService",
    "SqlFormattingService",
    "StatementSelection",
    "StatementService",
    "StatementSpan",
]
