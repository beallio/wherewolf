"""Subprocess guards for imports that must remain usable without the desktop stack."""

from __future__ import annotations

import subprocess
import sys
import textwrap


def _run_import_probe(code: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_execution_registry_import_is_free_of_qt_and_pyspark() -> None:
    _run_import_probe(
        """
        import sys
        import wherewolf.execution.registry

        forbidden = [
            name for name in sys.modules if name.startswith(("PyQt6", "pyspark"))
        ]
        if forbidden:
            raise SystemExit("forbidden modules loaded: " + ", ".join(forbidden))
        """
    )


def test_catalog_service_import_is_free_of_qt_and_pyspark() -> None:
    _run_import_probe(
        """
        import sys
        import wherewolf.services.catalog_service

        forbidden = [
            name for name in sys.modules if name.startswith(("PyQt6", "pyspark"))
        ]
        if forbidden:
            raise SystemExit("forbidden modules loaded: " + ", ".join(forbidden))
        """
    )


def test_settings_service_export_is_lazy_but_preserves_the_existing_class() -> None:
    _run_import_probe(
        """
        import sys
        from wherewolf.services import SettingsService
        from wherewolf.services.settings_service import SettingsService as ConcreteSettingsService

        if SettingsService is not ConcreteSettingsService:
            raise SystemExit("SettingsService export does not resolve to the concrete class")
        if not any(name.startswith("PyQt6") for name in sys.modules):
            raise SystemExit("SettingsService did not load Qt when explicitly requested")
        """
    )


def test_existing_services_exports_remain_importable() -> None:
    _run_import_probe(
        """
        from wherewolf.services import (
            CatalogService,
            CatalogServiceReport,
            ExecutionRequestBuilder,
            ExportFormat,
            FormattingResult,
            SettingsService,
            SqlCompletionService,
            SqlFormattingService,
            StatementSelection,
            StatementService,
            StatementSpan,
            export_file_filter,
            normalise_destination,
            serialise_history_records_to_sql,
            write_atomically,
            write_preview,
            write_selection,
        )
        """
    )
