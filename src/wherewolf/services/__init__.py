"""Service-layer entrypoints for desktop settings persistence."""

from .catalog_service import CatalogService, CatalogServiceReport
from .completion_service import SqlCompletionService
from .execution_request_builder import ExecutionRequestBuilder
from .export_destination import (
    ExportFormat,
    export_file_filter,
    normalise_destination,
    write_atomically,
)
from .formatting_service import FormattingResult, SqlFormattingService
from .history_sql_export import serialise_history_records_to_sql
from .preview_export import write_preview, write_selection
from .settings_service import SettingsService
from .statement_service import StatementSelection, StatementService, StatementSpan

__all__ = [
    "CatalogService",
    "CatalogServiceReport",
    "ExecutionRequestBuilder",
    "ExportFormat",
    "FormattingResult",
    "SettingsService",
    "SqlCompletionService",
    "SqlFormattingService",
    "StatementSelection",
    "StatementService",
    "StatementSpan",
    "export_file_filter",
    "normalise_destination",
    "serialise_history_records_to_sql",
    "write_atomically",
    "write_preview",
    "write_selection",
]
