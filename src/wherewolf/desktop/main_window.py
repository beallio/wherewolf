"""Main PyQt6 window for the desktop shell."""

from __future__ import annotations

import webbrowser
from importlib.metadata import version
from pathlib import Path
from typing import cast

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QFont, QStandardItemModel
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from sqlglot.dialects import DIALECT_MODULE_NAMES

from wherewolf.constants import DIALECT_MAPPING
from wherewolf.desktop.actions import DesktopActions, build_actions
from wherewolf.desktop.dialogs import FileDialogService, QtFileDialogService
from wherewolf.desktop.export_controller import ExportController, ExportResult
from wherewolf.desktop.query_controller import QueryController
from wherewolf.desktop.widgets import CatalogDock, HistoryDock, SqlEditor
from wherewolf.desktop.widgets.messages_panel import MessagesPanel
from wherewolf.desktop.widgets.result_table_view import ResultTableView
from wherewolf.desktop.widgets.schema_panel import SchemaPanel
from wherewolf.desktop.widgets.translation_panel import TranslationPanel
from wherewolf.desktop.workers import SchemaWorker
from wherewolf.domain import (
    CatalogBinding,
    EngineKind,
    ExecutionRequest,
    ExecutionStatus,
    QueryResult,
    SchemaResult,
    SqlDiagnostic,
    TranslationError,
)
from wherewolf.execution.registry import EngineRegistry
from wherewolf.services import (
    CatalogService,
    ExecutionRequestBuilder,
    ExportFormat,
    SettingsService,
)
from wherewolf.services.identifier_quoting import quote_identifier
from wherewolf.services.order_by_builder import build_order_by_sql
from wherewolf.services.preview_export import write_selection
from wherewolf.storage.history import HistoryManager


class FindReplaceDialog(QDialog):
    """Small non-modal bridge from Edit commands to the editor's existing helpers."""

    def __init__(self, editor: SqlEditor, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find / Replace")
        self._editor = editor
        layout = QFormLayout(self)
        self.find_input = QLineEdit(self)
        self.replace_input = QLineEdit(self)
        self.find_next_button = QPushButton("Find Next", self)
        self.replace_next_button = QPushButton("Replace Next", self)
        self.replace_all_button = QPushButton("Replace All", self)
        layout.addRow("Find", self.find_input)
        layout.addRow("Replace", self.replace_input)
        layout.addRow(self.find_next_button, self.replace_next_button)
        layout.addRow(self.replace_all_button)
        self.find_next_button.clicked.connect(lambda: editor.find_text(self.find_input.text()))
        self.replace_next_button.clicked.connect(
            lambda: editor.replace_next(self.find_input.text(), self.replace_input.text())
        )
        self.replace_all_button.clicked.connect(
            lambda: editor.replace_all(self.find_input.text(), self.replace_input.text())
        )


class PreferencesDialog(QDialog):
    """Persisted desktop editor/completion preferences."""

    def __init__(self, settings_service: SettingsService, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        layout = QFormLayout(self)
        self.font_size = QSpinBox(self)
        self.font_size.setRange(6, 64)
        self.font_size.setValue(settings_service.restore_editor_font_size())
        self.completion_enabled = QCheckBox("Enable completion", self)
        self.completion_enabled.setChecked(settings_service.restore_completion_enabled())
        self.completion_threshold = QSpinBox(self)
        self.completion_threshold.setRange(1, 20)
        self.completion_threshold.setValue(settings_service.restore_completion_threshold())
        layout.addRow("Editor font size", self.font_size)
        layout.addRow(self.completion_enabled)
        layout.addRow("Completion threshold", self.completion_threshold)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class MainWindow(QMainWindow):
    """A stable, testable application shell for desktop migration phase 3."""

    def __init__(
        self,
        *,
        settings_service: SettingsService | None = None,
        actions: DesktopActions | None = None,
        catalog_service: CatalogService | None = None,
        file_dialog_service: FileDialogService | None = None,
        engine_registry: EngineRegistry | None = None,
        query_controller: QueryController | None = None,
        export_controller: ExportController | None = None,
        history_manager: HistoryManager | None = None,
    ) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._settings_service = settings_service or SettingsService()
        self._catalog_service = catalog_service or CatalogService()
        self._file_dialog_service = file_dialog_service or QtFileDialogService()
        self._engine_registry = engine_registry or EngineRegistry()
        self.desktop_actions = actions or build_actions(self)
        self.query_controller = query_controller or QueryController(
            engine_registry=self._engine_registry, parent=self
        )
        self.export_controller = export_controller or ExportController(
            self._engine_registry, parent=self
        )
        self._last_request: ExecutionRequest | None = None
        self._last_result: QueryResult | None = None
        self.history_manager = history_manager or HistoryManager()
        self._schema_workers: list[SchemaWorker] = []
        self.setWindowTitle(f"Wherewolf {version('wherewolf')}")

        self.main_toolbar = self._build_toolbar()
        self._catalog_dock_widget = self._build_catalog_dock()
        self.dataset_catalog_dock = self._catalog_dock_widget
        self._schema_dock_widget = self._build_schema_dock()
        self._history_dock_widget = self._build_history_dock()
        self._central_splitter = self._build_central_area()
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.setCentralWidget(self._central_splitter)
        self._build_menus()
        self._connect_actions()
        self._restore_state()
        self._update_catalog_affordances()

    @property
    def catalog(self) -> CatalogDock:
        widget = self._catalog_dock_widget.widget()
        assert isinstance(widget, CatalogDock)
        return widget

    @property
    def catalog_dock(self) -> QDockWidget:
        return self._catalog_dock_widget

    @property
    def catalog_view(self) -> QDockWidget:
        return self._catalog_dock_widget

    @property
    def schema_panel(self) -> SchemaPanel:
        widget = self._schema_dock_widget.widget()
        assert isinstance(widget, SchemaPanel)
        return widget

    @property
    def schema_dock(self) -> QDockWidget:
        return self._schema_dock_widget

    @property
    def history_dock(self) -> HistoryDock:
        widget = self._history_dock_widget.widget()
        assert isinstance(widget, HistoryDock)
        return widget

    @property
    def editor(self) -> SqlEditor:
        widget = self._central_splitter.widget(0)
        assert isinstance(widget, SqlEditor)
        return widget

    def _build_toolbar(self) -> QToolBar:
        toolbar = self.addToolBar("Primary")
        assert toolbar is not None
        toolbar.setObjectName("primary_toolbar")
        toolbar.addAction(self.desktop_actions.run)
        toolbar.addAction(self.desktop_actions.cancel)
        toolbar.addAction(self.desktop_actions.format_sql)
        toolbar.addAction(self.desktop_actions.add_datasets)
        toolbar.addAction(self.desktop_actions.export_preview)
        toolbar.addAction(self.desktop_actions.export_full)
        toolbar.addAction(self.desktop_actions.export_selection)
        self.engine_selector = QComboBox(toolbar)
        self.engine_selector.setObjectName("engine_selector")
        model = cast(QStandardItemModel, self.engine_selector.model())
        for descriptor in self._engine_registry.available_engines():
            label = descriptor.display_name
            if not descriptor.available:
                assert descriptor.unavailable_reason is not None
                label = f"{label} (unavailable: {descriptor.unavailable_reason})"
            self.engine_selector.addItem(label, descriptor.kind)
            item = model.item(self.engine_selector.count() - 1)
            assert item is not None
            item.setEnabled(descriptor.available)
        toolbar.addWidget(self.engine_selector)
        self.input_dialect_selector = QComboBox(toolbar)
        self.input_dialect_selector.setObjectName("input_dialect_selector")
        for label, dialect in DIALECT_MAPPING.items():
            self.input_dialect_selector.addItem(label, dialect)
        toolbar.addWidget(self.input_dialect_selector)
        self.export_format_selector = QComboBox(toolbar)
        self.export_format_selector.setObjectName("export_format_selector")
        for label, export_format in (
            ("CSV", ExportFormat.CSV),
            ("Excel", ExportFormat.XLSX),
            ("Parquet", ExportFormat.PARQUET),
        ):
            self.export_format_selector.addItem(label, export_format)
        toolbar.addWidget(self.export_format_selector)
        self.preview_limit_selector = QSpinBox(toolbar)
        self.preview_limit_selector.setObjectName("preview_limit_selector")
        self.preview_limit_selector.setRange(10, 1000)
        self.preview_limit_selector.setValue(self._settings_service.restore_preview_limit())
        self.preview_limit_selector.valueChanged.connect(self._settings_service.save_preview_limit)
        toolbar.addWidget(self.preview_limit_selector)
        self.editor_theme_selector = QComboBox(toolbar)
        self.editor_theme_selector.setObjectName("editor_theme_selector")
        self.editor_theme_selector.addItems(SqlEditor.THEME_NAMES)
        self.editor_theme_selector.setCurrentText(self._settings_service.restore_editor_theme())
        toolbar.addWidget(self.editor_theme_selector)
        return toolbar

    def _build_catalog_dock(self) -> QDockWidget:
        catalog = CatalogDock(self._catalog_service, self)
        catalog.error_reported.connect(self._show_status)
        catalog.refresh_schema_requested.connect(self._on_refresh_catalog_schema)
        catalog.insert_alias_requested.connect(self.editor_insert_text)

        dock = QDockWidget("Dataset Catalog", self)
        dock.setObjectName("dataset_catalog_dock")
        dock.setWidget(catalog)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        return dock

    def _build_history_dock(self) -> QDockWidget:
        history_dock = HistoryDock(self.history_manager, self)
        history_dock.record_selected.connect(self._restore_history_query)

        dock = QDockWidget("History", self)
        dock.setObjectName("history_dock")
        dock.setWidget(history_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        return dock

    def _build_schema_dock(self) -> QDockWidget:
        schema_panel = SchemaPanel(self)
        schema_panel.insert_columns_requested.connect(self.editor_insert_text)

        dock = QDockWidget("Schema", self)
        dock.setObjectName("schema_dock")
        dock.setWidget(schema_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.tabifyDockWidget(self._catalog_dock_widget, dock)
        self._catalog_dock_widget.raise_()
        return dock

    def _connect_actions(self) -> None:
        self.desktop_actions.add_datasets.triggered.connect(self._on_add_datasets)
        self.desktop_actions.reset_layout.triggered.connect(self._reset_layout)
        self.desktop_actions.clear_history.triggered.connect(self._clear_history)
        self.desktop_actions.run.triggered.connect(self._on_run_triggered)
        self.desktop_actions.cancel.triggered.connect(self._on_cancel_triggered)
        self.desktop_actions.export_preview.triggered.connect(lambda: self._start_export(False))
        self.desktop_actions.export_full.triggered.connect(lambda: self._start_export(True))
        self.desktop_actions.export_selection.triggered.connect(self._export_selection)

        self.query_controller.status_changed.connect(self._on_query_status_changed)
        self.query_controller.result_ready.connect(self._on_query_result_ready)
        self.export_controller.started.connect(self._on_export_started)
        self.export_controller.result_ready.connect(self._on_export_result)

    def _on_run_triggered(self) -> None:
        sql, _start, _end = self.editor.text_to_run()
        if not sql or not sql.strip():
            self._show_status("No SQL statement to run", 5000)
            return

        try:
            engine = cast(EngineKind, self.engine_selector.currentData())
            source_dialect = self.input_dialect_selector.currentData()
            if not isinstance(source_dialect, str):
                raise TypeError("No input dialect is selected")
            request = ExecutionRequestBuilder.build(
                sql=sql,
                source_dialect=source_dialect,
                engine=engine,
                catalog_service=self._catalog_service,
                preview_limit=self.preview_limit_selector.value(),
            )
        except TranslationError as exc:
            self._on_editor_diagnostics(
                (
                    SqlDiagnostic(
                        message=str(exc),
                        severity="error",
                        start_line=1,
                        start_column=1,
                    ),
                )
            )
            return
        except Exception as exc:  # noqa: BLE001  # Request creation boundary
            self._show_status(f"Failed to prepare query: {exc}", 5000)
            return

        self.query_controller.execute(request)

    def _on_cancel_triggered(self) -> None:
        if not self.export_controller.cancel():
            self.query_controller.cancel()

    def _on_query_status_changed(self, status: ExecutionStatus) -> None:
        if status in (ExecutionStatus.RUNNING, ExecutionStatus.CANCELLATION_REQUESTED):
            self.desktop_actions.run.setEnabled(False)
            self.desktop_actions.cancel.setEnabled(True)
            if status is ExecutionStatus.CANCELLATION_REQUESTED:
                self._show_status("Cancellation requested")
            else:
                self._show_status("Executing query...")
        else:
            self.desktop_actions.run.setEnabled(bool(self._catalog_service.entries))
            self.desktop_actions.cancel.setEnabled(False)

    def _on_query_result_ready(self, result: QueryResult, request: ExecutionRequest) -> None:
        self._last_request, self._last_result = request, result
        can_export = result.status is ExecutionStatus.SUCCEEDED and result.frame is not None
        self.desktop_actions.export_preview.setEnabled(can_export)
        self.desktop_actions.export_full.setEnabled(can_export)
        self.desktop_actions.export_selection.setEnabled(can_export)
        if result.status is ExecutionStatus.SUCCEEDED and result.frame is not None:
            self.result_table_view.set_frame(result.frame)
        else:
            self.result_table_view.set_frame(None)
        self.result_truncation_notice.setVisible(
            result.status is ExecutionStatus.SUCCEEDED and result.truncated
        )

        self.messages_panel.show_query_result(result)

        engine_name = (
            "DuckDB" if request.engine is EngineKind.DUCKDB else request.engine.value.title()
        )
        if result.status is ExecutionStatus.SUCCEEDED:
            catalog_dict = {b.alias: str(b.path) for b in request.catalog}
            self.history_manager.add_entry(
                engine=request.engine.value,
                query=request.original_sql,
                catalog=catalog_dict,
            )
            self.history_dock.refresh()

            trunc_str = " (truncated)" if result.truncated else ""
            msg = (
                f"Engine: {engine_name} | State: Succeeded | Elapsed: {result.execution_seconds:.2f}s | "
                f"Preview Rows: {result.preview_row_count}{trunc_str}"
            )
            self._show_status(msg, 10000)
        elif result.status is ExecutionStatus.FAILED:
            self._show_status(
                f"Engine: {engine_name} | State: Failed | Elapsed: {result.execution_seconds:.2f}s | Error: {result.error_message}",
                10000,
            )
        elif result.status is ExecutionStatus.CANCELLED:
            self._show_status(
                f"Engine: {engine_name} | State: Cancelled | Elapsed: {result.execution_seconds:.2f}s | Cancellation completed",
                10000,
            )

    def _start_export(self, full_export: bool) -> None:
        if (
            self._last_result is None
            or self._last_result.frame is None
            or self._last_request is None
        ):
            return
        choose_export_path = getattr(self._file_dialog_service, "choose_export_path", None)
        if choose_export_path is None:
            self._show_status("Export dialog is unavailable", 5000)
            return
        export_format = self.export_format_selector.currentData()
        if not isinstance(export_format, ExportFormat):
            self._show_status("No export format is selected", 5000)
            return
        destination = choose_export_path(None, export_format, self)
        if destination is not None:
            self.export_controller.export(
                self._last_request,
                self._last_result.frame,
                destination,
                export_format,
                full_export,
            )

    def _export_selection(self) -> None:
        if not self.result_table_view.has_result():
            return
        frame = self.result_table_view.frame()
        selected_cells, column_order = self.result_table_view.selection_for_export()
        if not selected_cells:
            self._show_status("Select result cells to export", 5000)
            return
        choose_export_path = getattr(self._file_dialog_service, "choose_export_path", None)
        export_format = self.export_format_selector.currentData()
        if choose_export_path is None or not isinstance(export_format, ExportFormat):
            return
        destination = choose_export_path(None, export_format, self)
        if destination is None:
            return
        write_selection(frame, selected_cells, column_order, destination, export_format)
        self._show_status(f"Exported selection to {destination}")

    def _on_export_started(self) -> None:
        self.desktop_actions.cancel.setEnabled(True)
        self.desktop_actions.export_preview.setEnabled(False)
        self.desktop_actions.export_full.setEnabled(False)
        self.desktop_actions.export_selection.setEnabled(False)
        self._show_status("Exporting results...")

    def _on_export_result(self, result: ExportResult) -> None:
        self.desktop_actions.cancel.setEnabled(False)
        can_export = self._last_result is not None and self._last_result.frame is not None
        self.desktop_actions.export_preview.setEnabled(can_export)
        self.desktop_actions.export_full.setEnabled(can_export)
        self.desktop_actions.export_selection.setEnabled(can_export)
        if result.succeeded:
            message = f"Exported results to {result.destination}"
            if result.warnings:
                # registry._source_warnings flags a source file that changed under the
                # export. Reporting bare success there hands the user a stale artifact
                # they believe is current.
                message = "\n".join((message, *sorted(set(result.warnings))))
            self._show_status(message)
        else:
            self._show_status(f"Export failed: {result.error_message}")

    def _on_add_datasets(self) -> None:
        chooser = self._file_dialog_service.choose_dataset_files
        default_directory = self._settings_service.restore_last_dataset_directory()
        if self.show_hidden_files_action.isChecked() and isinstance(
            self._file_dialog_service, QtFileDialogService
        ):
            paths = self._file_dialog_service.choose_dataset_files(
                default_directory=default_directory, parent=self, show_hidden=True
            )
        else:
            paths = chooser(default_directory=default_directory, parent=self)

        if not paths:
            return

        was_empty_catalog = not self._catalog_service.entries
        result = self._catalog_service.add_paths(paths)
        if result.added:
            first = result.added[0]
            if was_empty_catalog and not self.editor.text().strip():
                self.editor.setText(f"SELECT * FROM {quote_identifier(first.alias)} LIMIT 10")
            self._settings_service.save_last_dataset_directory(first.path.parent)
            for entry in result.added:
                self._queue_schema_work(
                    CatalogBinding(
                        entry_id=entry.id,
                        alias=entry.alias,
                        path=entry.path,
                        source_format=entry.source_format,
                    )
                )
            self._show_status(f"Added `{first.alias}` to catalog.")
            self._update_catalog_affordances()
        if result.warnings:
            self._show_status("\n".join(sorted(set(result.warnings))))

    def _on_refresh_catalog_schema(self, binding: CatalogBinding) -> None:
        self._queue_schema_work(binding)

    def _queue_schema_work(self, binding: CatalogBinding) -> None:
        worker = SchemaWorker(
            engine_registry=self._engine_registry,
            binding=binding,
            parent=self,
        )
        worker.result_ready.connect(self._on_schema_result)
        worker.finished.connect(
            lambda: self._schema_workers.remove(worker) if worker in self._schema_workers else None
        )
        self._schema_workers.append(worker)
        worker.start()

    def _on_schema_result(self, schema_result: SchemaResult) -> None:
        self._catalog_service.update_schema(schema_result)
        self.editor.set_catalog(self._catalog_service.entries)
        self.schema_panel.set_schema_result(schema_result)

    def _build_central_area(self) -> QSplitter:
        editor = SqlEditor(
            settings_service=self._settings_service,
            format_action=self.desktop_actions.format_sql,
            show_completion_action=self.desktop_actions.show_completion,
            parent=self,
        )
        editor.setObjectName("query_editor")
        editor.set_catalog(self._catalog_service.entries)
        editor.diagnostics_reported.connect(self._on_editor_diagnostics)

        results = QTabWidget(self)
        results.setObjectName("results_tabs")
        self.result_table_view = ResultTableView(self)
        self.result_table_view.setObjectName("result_table_view")
        self.result_table_view.insert_header_requested.connect(self.editor_insert_text)
        self.result_table_view.apply_query_order_requested.connect(self._on_apply_query_order)
        self.result_table_view.local_sort_changed.connect(self._set_local_sort_notice_visible)
        self.result_table_view.frame_changed.connect(
            self.desktop_actions.export_selection.setEnabled
        )
        results_page = QWidget(results)
        results_layout = QVBoxLayout(results_page)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.result_sort_notice = QLabel("Sorted preview only.", results_page)
        self.result_sort_notice.setObjectName("result_sort_notice")
        self.result_sort_notice.setVisible(False)
        results_layout.addWidget(self.result_sort_notice)
        self.result_truncation_notice = QLabel(
            "Preview is truncated at the selected row limit. Export Full Results for all rows.",
            results_page,
        )
        self.result_truncation_notice.setObjectName("result_truncation_notice")
        self.result_truncation_notice.setVisible(False)
        results_layout.addWidget(self.result_truncation_notice)
        self.preview_filter_input = QLineEdit(results_page)
        self.preview_filter_input.setObjectName("preview_filter_input")
        self.preview_filter_input.setPlaceholderText("Filter preview rows")
        self.clear_preview_filter_action = QAction("Clear Preview Filter", self)
        self.clear_preview_filter_action.triggered.connect(self.preview_filter_input.clear)
        self.preview_filter_input.textChanged.connect(
            self.result_table_view.proxy_model().set_filter_text
        )
        results_layout.addWidget(self.preview_filter_input)
        results_layout.addWidget(self.result_table_view)
        results.addTab(results_page, "Results")
        self.messages_panel = MessagesPanel(self)
        self.messages_panel.setObjectName("messages_panel")
        results.addTab(self.messages_panel, "Messages")

        translation_page = QWidget(results)
        translation_layout = QVBoxLayout(translation_page)
        translation_controls = QHBoxLayout()
        translation_controls.addWidget(QLabel("Target Dialect", translation_page))
        self.translation_target_selector = QComboBox(translation_page)
        self.translation_target_selector.setObjectName("translation_target_selector")
        for dialect in sorted(DIALECT_MODULE_NAMES):
            self.translation_target_selector.addItem(dialect, dialect)
        spark_index = self.translation_target_selector.findData("spark")
        self.translation_target_selector.setCurrentIndex(max(spark_index, 0))
        translation_controls.addWidget(self.translation_target_selector)
        translation_layout.addLayout(translation_controls)
        self.translation_panel = TranslationPanel(translation_page)
        self.translation_panel.setObjectName("translation_panel")
        translation_layout.addWidget(self.translation_panel)
        self.translation_target_selector.currentTextChanged.connect(self._refresh_translation)
        self.input_dialect_selector.currentTextChanged.connect(self._refresh_translation)
        self.editor_theme_selector.currentTextChanged.connect(editor.set_theme)
        editor.textChanged.connect(self._refresh_translation)
        editor.textChanged.connect(self._update_catalog_affordances)
        results.addTab(translation_page, "Translation")

        self.empty_catalog_banner = QLabel("Please add a dataset to begin.", results)
        self.empty_catalog_banner.setObjectName("empty_catalog_banner")
        results_layout.insertWidget(0, self.empty_catalog_banner)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setObjectName("central_splitter")
        splitter.addWidget(editor)
        splitter.addWidget(results)
        return splitter

    def _set_local_sort_notice_visible(self, is_sorted: bool) -> None:
        self.result_sort_notice.setVisible(is_sorted)

    def _refresh_translation(self) -> None:
        target_dialect = self.translation_target_selector.currentData()
        if not isinstance(target_dialect, str):
            return
        source_dialect = self.input_dialect_selector.currentData()
        if not isinstance(source_dialect, str):
            return
        self.translation_panel.update_translation(
            self.editor.text(), source_dialect=source_dialect, target_dialect=target_dialect
        )

    def editor_insert_text(self, alias: str) -> None:
        self.editor.insert(alias)

    def _restore_history_query(self, record: dict) -> None:
        """Place a historical SQL statement in the editor without running it."""
        query = record.get("query")
        if isinstance(query, str):
            self.editor.setText(query)
        self._restore_history_catalog(record)

    def _restore_history_catalog(self, record: dict) -> None:
        """Restore available historical datasets and make unavailable paths visible."""
        catalog = record.get("catalog")
        if not isinstance(catalog, dict):
            return

        available_paths: list[Path] = []
        missing_paths: list[Path] = []
        for raw_path in catalog.values():
            if not isinstance(raw_path, str) or not raw_path:
                continue
            path = Path(raw_path)
            if path.exists():
                available_paths.append(path)
            else:
                missing_paths.append(path)

        if available_paths:
            result = self._catalog_service.add_paths(tuple(available_paths))
            for entry in result.added:
                self._queue_schema_work(
                    CatalogBinding(
                        entry_id=entry.id,
                        alias=entry.alias,
                        path=entry.path,
                        source_format=entry.source_format,
                    )
                )
            self.editor.set_catalog(self._catalog_service.entries)

        if missing_paths:
            self._show_status(
                "Missing history dataset(s): " + ", ".join(str(path) for path in missing_paths),
                10000,
            )

    def _on_apply_query_order(self, column_name: str, direction: str) -> None:
        if not self.result_table_view.has_result():
            return
        current_sql = self.editor.text()
        if not current_sql.strip():
            return
        ordered_sql = build_order_by_sql(current_sql, column_name, direction)
        self.editor.setText(ordered_sql)
        self._on_run_triggered()

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        assert menu_bar is not None
        file_menu = cast(QMenu, menu_bar.addMenu("File"))
        file_menu.setObjectName("file_menu")
        file_menu.addAction(self.desktop_actions.clear_history)

        edit_menu = cast(QMenu, menu_bar.addMenu("Edit"))
        edit_menu.setObjectName("edit_menu")
        undo, redo, cut, copy, paste, toggle_comment = self.editor.edit_actions
        edit_menu.addAction(undo)
        edit_menu.addAction(redo)
        edit_menu.addSeparator()
        edit_menu.addAction(cut)
        edit_menu.addAction(copy)
        edit_menu.addAction(paste)
        self.select_all_action = QAction("Select All", self)
        self.select_all_action.triggered.connect(self.editor.selectAll)
        self.find_replace_action = QAction("Find / Replace…", self)
        self.find_replace_action.triggered.connect(self._show_find_replace)
        edit_menu.addAction(self.select_all_action)
        edit_menu.addAction(self.find_replace_action)
        edit_menu.addSeparator()
        edit_menu.addAction(toggle_comment)

        query_menu = cast(QMenu, menu_bar.addMenu("Query"))
        query_menu.setObjectName("query_menu")
        query_menu.addAction(self.desktop_actions.run)
        query_menu.addAction(self.desktop_actions.cancel)
        query_menu.addAction(self.desktop_actions.format_sql)
        query_menu.addAction(self.desktop_actions.show_completion)

        view_menu = cast(QMenu, menu_bar.addMenu("View"))
        view_menu.setObjectName("view_menu")
        view_menu.addAction(self.desktop_actions.reset_layout)
        view_menu.addAction(self.clear_preview_filter_action)
        self.show_hidden_files_action = QAction("Show Hidden Files", self)
        self.show_hidden_files_action.setCheckable(True)
        view_menu.addAction(self.show_hidden_files_action)
        self.preferences_action = QAction("Preferences…", self)
        self.preferences_action.triggered.connect(self._show_preferences)
        view_menu.addAction(self.preferences_action)

        help_menu = cast(QMenu, menu_bar.addMenu("Help"))
        help_menu.setObjectName("help_menu")
        self.about_action = help_menu.addAction("About")
        assert self.about_action is not None
        self.about_action.triggered.connect(self._show_about)
        self.documentation_action = help_menu.addAction("Documentation")
        assert self.documentation_action is not None
        self.documentation_action.triggered.connect(
            lambda: webbrowser.open("https://github.com/beallio/wherewolf#readme")
        )
        self.licenses_action = help_menu.addAction("Open-Source Licenses")
        assert self.licenses_action is not None
        self.licenses_action.triggered.connect(self._show_licenses)

        self.file_menu = file_menu
        self.edit_menu = edit_menu
        self.query_menu = query_menu
        self.view_menu = view_menu
        self.help_menu = help_menu

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Wherewolf",
            "Wherewolf is licensed under GPL-3.0-only.\n\n"
            "Pre-0.6 MIT terms are retained in LICENSES/MIT-pre-0.6.txt.",
        )

    def _show_licenses(self) -> None:
        QMessageBox.about(
            self, "Open-Source Licenses", "See LICENSE and LICENSES in the application source."
        )

    def _show_find_replace(self) -> None:
        self.find_replace_dialog = FindReplaceDialog(self.editor, self)
        self.find_replace_dialog.show()

    def _show_preferences(self) -> None:
        self.preferences_dialog = PreferencesDialog(self._settings_service, self)
        self.preferences_dialog.accepted.connect(self._apply_preferences)
        self.preferences_dialog.show()

    def _apply_preferences(self) -> None:
        dialog = self.preferences_dialog
        self._settings_service.save_completion_enabled(dialog.completion_enabled.isChecked())
        self._settings_service.save_completion_threshold(dialog.completion_threshold.value())
        self.editor.set_font_size(dialog.font_size.value())

    def _on_editor_diagnostics(self, payload: tuple) -> None:
        for diagnostic in payload:
            self.messages_panel.add_diagnostic(diagnostic)
        if payload:
            self._show_status(payload[0].message, 5000)

    def _update_catalog_affordances(self) -> None:
        has_datasets = bool(self._catalog_service.entries)
        self.desktop_actions.run.setEnabled(has_datasets)
        self.empty_catalog_banner.setVisible(not has_datasets)

    def _restore_state(self) -> None:
        geometry = self._settings_service.restore_window_geometry()
        if geometry:
            self.restoreGeometry(QByteArray(geometry))

        state = self._settings_service.restore_window_state()
        if state:
            self.restoreState(QByteArray(state))

        sizes = self._settings_service.restore_splitter_sizes()
        if sizes:
            self._central_splitter.setSizes(list(sizes))

        font_size = self._settings_service.restore_editor_font_size()
        self.editor.set_font_size(font_size)

    def _reset_layout(self) -> None:
        """Return persistent docks and the central splitter to their default arrangement."""
        for dock, area in (
            (self._catalog_dock_widget, Qt.DockWidgetArea.LeftDockWidgetArea),
            (self._schema_dock_widget, Qt.DockWidgetArea.LeftDockWidgetArea),
            (self._history_dock_widget, Qt.DockWidgetArea.RightDockWidgetArea),
        ):
            dock.setFloating(False)
            self.addDockWidget(area, dock)
            dock.show()
        self._central_splitter.setSizes(list(self._settings_service.DEFAULT_SPLITTER_SIZES))
        self._settings_service.save_window_state(self.saveState().data())
        self._settings_service.save_splitter_sizes(self._central_splitter.sizes())

    def _clear_history(self) -> None:
        """Atomically clear persisted history and synchronize the dock immediately."""
        self.history_manager.clear()
        self.history_dock.refresh()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        for worker in list(self._schema_workers):
            if worker.isRunning():
                worker.quit()
                worker.wait()
        self._schema_workers.clear()

        self.query_controller.shutdown()
        self.export_controller.shutdown()

        self._settings_service.save_window_geometry(self.saveGeometry().data())
        self._settings_service.save_window_state(self.saveState().data())
        self._settings_service.save_splitter_sizes(self._central_splitter.sizes())
        font = self.editor.font()
        if isinstance(font, QFont):
            self._settings_service.save_editor_font_size(font.pointSize())
        super().closeEvent(a0)

    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:
        if a0 is None:
            return
        self.catalog.dragEnterEvent(a0)

    def dropEvent(self, a0: QDropEvent | None) -> None:
        if a0 is None:
            return
        self.catalog.dropEvent(a0)

    def _show_status(self, message: str, timeout: int = 3000) -> None:
        self.status_bar.showMessage(message, timeout)
