"""Service-layer entrypoints with desktop-only imports kept lazy."""

from typing import TYPE_CHECKING

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
from .statement_service import StatementSelection, StatementService, StatementSpan

if TYPE_CHECKING:
    from .settings_service import SettingsService

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


def __getattr__(name: str):
    """Load desktop settings only when its public export is explicitly requested."""
    if name == "SettingsService":
        from .settings_service import SettingsService

        return SettingsService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
