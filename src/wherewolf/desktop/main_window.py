"""Main PyQt6 window for the desktop shell."""

from __future__ import annotations

import time
import webbrowser
from importlib.metadata import version
from typing import cast

from PyQt6.QtCore import QByteArray, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIntValidator,
    QKeySequence,
    QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QApplication,
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

from wherewolf import build_identifier
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
from wherewolf.desktop.workers import ProfileWorker, SchemaWorker
from wherewolf.domain import (
    CatalogBinding,
    EngineKind,
    ExecutionRequest,
    ExecutionStatus,
    ProfileResult,
    QueryResult,
    SchemaResult,
    SqlDiagnostic,
    TranslationError,
)
from wherewolf.execution.registry import EngineRegistry
from wherewolf.services import (
    CatalogService,
    CatalogServiceReport,
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
        self.profile_on_load = QCheckBox("Profile datasets when added", self)
        self.profile_on_load.setChecked(settings_service.restore_profile_on_load())
        self.profile_max_bytes = QSpinBox(self)
        self.profile_max_bytes.setRange(0, 2_147_483_647)
        self.profile_max_bytes.setValue(settings_service.restore_profile_max_bytes())
        self.editor_theme_selector = QComboBox(self)
        self.editor_theme_selector.setObjectName("editor_theme_selector")
        self.editor_theme_selector.addItems(SqlEditor.THEME_NAMES)
        self.editor_theme_selector.setCurrentText(settings_service.restore_editor_theme())
        layout.addRow("Editor font size", self.font_size)
        layout.addRow(self.completion_enabled)
        layout.addRow("Completion threshold", self.completion_threshold)
        layout.addRow(self.profile_on_load)
        layout.addRow("Profile size limit (bytes)", self.profile_max_bytes)
        layout.addRow("Editor theme", self.editor_theme_selector)
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
        self._profile_workers: list[ProfileWorker] = []
        self.setWindowTitle(f"Wherewolf {version('wherewolf')}")

        self.main_toolbar = self._build_toolbar()
        self.query_controls_toolbar = self._build_query_controls_toolbar()
        self._catalog_dock_widget = self._build_catalog_dock()
        self.dataset_catalog_dock = self._catalog_dock_widget
        self._schema_dock_widget = self._build_schema_dock()
        self._history_dock_widget = self._build_history_dock()
        self._central_splitter = self._build_central_area()
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed_status)
        self._query_started_at: float | None = None

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
        return toolbar

    def _build_query_controls_toolbar(self) -> QToolBar:
        """Place compact query controls on their own toolbar row.

        Keeping controls on a dedicated row prevents Qt's toolbar overflow menu
        from hiding them at normal desktop window widths.
        """
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        toolbar = self.addToolBar("Query Controls")
        assert toolbar is not None
        toolbar.setObjectName("query_controls_toolbar")
        controls = QWidget(toolbar)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(4, 0, 4, 0)
        controls_layout.setSpacing(8)

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
        self._add_labelled_control(
            controls_layout,
            "Execution engine",
            self.engine_selector,
            "Choose where the query runs: DuckDB or Spark.",
        )
        self.input_dialect_selector = QComboBox(toolbar)
        self.input_dialect_selector.setObjectName("input_dialect_selector")
        for label, dialect in DIALECT_MAPPING.items():
            self.input_dialect_selector.addItem(label, dialect)
        self._add_labelled_control(
            controls_layout,
            "Input dialect",
            self.input_dialect_selector,
            "Choose the SQL dialect you are writing; it is transpiled to the execution engine.",
        )
        self._preview_limit_value = self._settings_service.restore_preview_limit()
        self.preview_limit_selector = QLineEdit(toolbar)
        self.preview_limit_selector.setObjectName("preview_limit_selector")
        self.preview_limit_selector.setValidator(
            QIntValidator(
                SettingsService.MIN_PREVIEW_LIMIT,
                SettingsService.MAX_PREVIEW_LIMIT,
                self.preview_limit_selector,
            )
        )
        self.preview_limit_selector.setText(str(self._preview_limit_value))
        self.preview_limit_selector.textChanged.connect(self._on_preview_limit_changed)
        self._set_preview_limit_validity(True)
        self._add_labelled_control(
            controls_layout,
            "Preview rows",
            self.preview_limit_selector,
            "Choose the maximum number of rows shown in a query preview.",
        )
        toolbar.addWidget(controls)
        return toolbar

    def _on_preview_limit_changed(self, text: str) -> None:
        if text.isdecimal():
            value = int(text)
            if SettingsService.MIN_PREVIEW_LIMIT <= value <= SettingsService.MAX_PREVIEW_LIMIT:
                self._preview_limit_value = value
                self._settings_service.save_preview_limit(value)
                self._set_preview_limit_validity(True)
                return
        self._set_preview_limit_validity(False)

    def _set_preview_limit_validity(self, valid: bool) -> None:
        self.preview_limit_selector.setProperty("validationState", "valid" if valid else "invalid")
        if valid:
            self.preview_limit_selector.setStyleSheet("")
            self.preview_limit_selector.setToolTip(
                "Choose the maximum number of rows shown in a query preview (10–100000)."
            )
        else:
            self.preview_limit_selector.setStyleSheet(
                "QLineEdit[validationState='invalid'] { border: 1px solid #d7191c; }"
            )
            self.preview_limit_selector.setToolTip(
                "Enter a whole number from 10 to 100000 for preview rows."
            )

    @staticmethod
    def _add_labelled_control(
        layout: QHBoxLayout,
        caption: str,
        control: QWidget,
        tooltip: str,
    ) -> None:
        control.setToolTip(tooltip)
        label = QLabel(caption, control.parentWidget())
        label.setObjectName(f"{control.objectName()}_label")
        label.setToolTip(tooltip)
        label.setBuddy(control)
        layout.addWidget(label)
        layout.addWidget(control)

    def _build_catalog_dock(self) -> QDockWidget:
        catalog = CatalogDock(self._catalog_service, self)
        catalog.datasets_added.connect(self._handle_add_result)
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
        schema_panel.profile_requested.connect(
            lambda entry: self._queue_profile_work(
                CatalogBinding(entry.id, entry.alias, entry.path, entry.source_format)
            )
        )

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
                preview_limit=self._preview_limit_value,
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
        if status is ExecutionStatus.RUNNING:
            self._query_started_at = time.monotonic()
            self._elapsed_timer.start()
            self.desktop_actions.run.setEnabled(False)
            self.desktop_actions.cancel.setEnabled(True)
            self._show_status("Executing query...")
        elif status is ExecutionStatus.CANCELLATION_REQUESTED:
            self.desktop_actions.run.setEnabled(False)
            self.desktop_actions.cancel.setEnabled(True)
            self._show_status("Cancellation requested")
        else:
            self._elapsed_timer.stop()
            self._query_started_at = None
            self.desktop_actions.run.setEnabled(bool(self._catalog_service.entries))
            self.desktop_actions.cancel.setEnabled(False)

    def _update_elapsed_status(self) -> None:
        if self._query_started_at is None:
            return
        elapsed_seconds = max(0, int(time.monotonic() - self._query_started_at))
        self._show_status(f"Executing query... ({elapsed_seconds}s)")

    def _on_query_result_ready(self, result: QueryResult, request: ExecutionRequest) -> None:
        self._last_request, self._last_result = request, result
        can_export = result.status is ExecutionStatus.SUCCEEDED and result.frame is not None
        self.desktop_actions.export_preview.setEnabled(can_export)
        self.desktop_actions.export_full.setEnabled(can_export)
        self.desktop_actions.export_selection.setEnabled(can_export)
        self.export_button.setEnabled(can_export)
        if result.status is ExecutionStatus.SUCCEEDED and result.frame is not None:
            self.result_table_view.set_frame(result.frame)
        else:
            self.result_table_view.set_frame(None)
        is_empty_result = (
            result.status is ExecutionStatus.SUCCEEDED
            and result.frame is not None
            and result.frame.height == 0
        )
        if is_empty_result:
            self.empty_result_banner.setText("Query returned 0 rows.")
        else:
            self.empty_result_banner.clear()
        self.empty_result_banner.setVisible(is_empty_result)
        if result.status is ExecutionStatus.FAILED:
            self.result_error_message.setText(
                f"Query failed: {result.error_message or 'Unknown error'}"
            )
            self.result_error_message.setVisible(True)
        else:
            self.result_error_message.clear()
            self.result_error_message.setVisible(False)
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

    def _export_selected_scope(self) -> None:
        scope = self.export_scope_selector.currentData()
        if scope == "preview":
            self._start_export(False)
        elif scope == "full":
            self._start_export(True)
        elif scope == "selection":
            self._export_selection()

    def _on_preview_filter_error(self, message: str) -> None:
        self.preview_filter_error.setText(message)
        self.preview_filter_error.setVisible(bool(message))

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
        self.export_button.setEnabled(False)
        self._show_status("Exporting results...")

    def _on_export_result(self, result: ExportResult) -> None:
        self.desktop_actions.cancel.setEnabled(False)
        can_export = self._last_result is not None and self._last_result.frame is not None
        self.desktop_actions.export_preview.setEnabled(can_export)
        self.desktop_actions.export_full.setEnabled(can_export)
        self.desktop_actions.export_selection.setEnabled(can_export)
        self.export_button.setEnabled(can_export)
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

        self.catalog.add_paths(paths)

    def _handle_add_result(self, result: CatalogServiceReport) -> None:
        duplicate_message = ""
        if result.duplicates:
            duplicate_names = ", ".join(path.name for path in result.duplicates)
            duplicate_message = (
                f"Skipped {len(result.duplicates)} duplicate dataset(s): {duplicate_names}"
            )
        if result.added:
            first = result.added[0]
            was_empty_catalog = len(self._catalog_service.entries) == len(result.added)
            if was_empty_catalog and not self.editor.text().strip():
                self.editor.setText(f"SELECT * FROM {quote_identifier(first.alias)}")
            self._settings_service.save_last_dataset_directory(first.path.parent)
            for entry in result.added:
                binding = CatalogBinding(entry.id, entry.alias, entry.path, entry.source_format)
                self._queue_schema_work(binding)
                if self._settings_service.restore_profile_on_load():
                    if (
                        entry.path.stat().st_size
                        <= self._settings_service.restore_profile_max_bytes()
                    ):
                        self._queue_profile_work(binding)
                    else:
                        self._catalog_service.mark_profile_skipped(
                            entry.id, "Profiling skipped: source exceeds the configured size limit."
                        )
            message = f"Added `{first.alias}` to catalog."
            if duplicate_message:
                message = f"{message} {duplicate_message}"
            self._show_status(message)
            self._update_catalog_affordances()
        elif duplicate_message:
            self._show_status(duplicate_message)
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

    def _queue_profile_work(self, binding: CatalogBinding) -> None:
        worker = ProfileWorker(
            engine_registry=self._engine_registry,
            binding=binding,
            parent=self,
        )
        worker.result_ready.connect(self._on_profile_result)
        worker.finished.connect(
            lambda: (
                self._profile_workers.remove(worker) if worker in self._profile_workers else None
            )
        )
        self._profile_workers.append(worker)
        worker.start()

    def _on_profile_result(self, profile_result: ProfileResult) -> None:
        self._catalog_service.update_profile(profile_result)
        self._catalog_service.refresh_profile_staleness()
        entry = next(
            (
                entry
                for entry in self._catalog_service.entries
                if entry.id == profile_result.entry_id
            ),
            None,
        )
        if entry is not None:
            self.schema_panel.set_entries(self._catalog_service.entries, entry.alias)

    def _on_schema_result(self, schema_result: SchemaResult) -> None:
        self._catalog_service.update_schema(schema_result)
        self.editor.set_catalog(self._catalog_service.entries)
        entry = next(
            (
                entry
                for entry in self._catalog_service.entries
                if entry.id == schema_result.entry_id
            ),
            None,
        )
        if entry is None:
            self.schema_panel.set_schema_result(schema_result)
        else:
            self.schema_panel.set_entries(self._catalog_service.entries, entry.alias)

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
        self.result_error_message = QLabel(results_page)
        self.result_error_message.setObjectName("result_error_message")
        self.result_error_message.setWordWrap(True)
        self.result_error_message.setVisible(False)
        results_layout.addWidget(self.result_error_message)
        self.preview_filter_input = QLineEdit(results_page)
        self.preview_filter_input.setObjectName("preview_filter_input")
        self.preview_filter_input.setPlaceholderText("Filter preview rows")
        self.preview_filter_input.setToolTip(
            "Filter the preview with a SQL predicate or plain text substring."
        )
        self.clear_preview_filter_action = QAction("Clear Preview Filter", self)
        self.clear_preview_filter_action.triggered.connect(self.preview_filter_input.clear)
        self.preview_filter_input.textChanged.connect(
            self.result_table_view.proxy_model().set_filter_text
        )
        self.result_table_view.proxy_model().filter_error_changed.connect(
            self._on_preview_filter_error
        )
        export_controls = QHBoxLayout()
        self._add_labelled_control(
            export_controls,
            "Preview filter",
            self.preview_filter_input,
            self.preview_filter_input.toolTip(),
        )

        self.export_format_selector = QComboBox(results_page)
        self.export_format_selector.setObjectName("export_format_selector")
        for label, export_format in (
            ("CSV", ExportFormat.CSV),
            ("Excel", ExportFormat.XLSX),
            ("Parquet", ExportFormat.PARQUET),
        ):
            self.export_format_selector.addItem(label, export_format)
        self._add_labelled_control(
            export_controls,
            "Export format",
            self.export_format_selector,
            "Choose the file format for exported query results.",
        )

        self.export_scope_selector = QComboBox(results_page)
        self.export_scope_selector.setObjectName("export_scope_selector")
        self.export_scope_selector.addItem("Preview", "preview")
        self.export_scope_selector.addItem("Full results", "full")
        self.export_scope_selector.addItem("Selection", "selection")
        self._add_labelled_control(
            export_controls,
            "Export scope",
            self.export_scope_selector,
            "Choose which result scope to export.",
        )

        self.export_button = QPushButton("Export", results_page)
        self.export_button.setObjectName("export_button")
        self.export_button.setToolTip("Export results using the selected format and scope.")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._export_selected_scope)
        export_controls.addWidget(self.export_button)

        export_controls.setStretch(1, 1)
        results_layout.addLayout(export_controls)
        self.preview_filter_error = QLabel(results_page)
        self.preview_filter_error.setObjectName("preview_filter_error")
        self.preview_filter_error.setWordWrap(True)
        self.preview_filter_error.setVisible(False)
        results_layout.addWidget(self.preview_filter_error)
        results_layout.addWidget(self.result_table_view)
        results.addTab(results_page, "Results")
        self.messages_panel = MessagesPanel(self)
        self.messages_panel.setObjectName("messages_panel")
        results.addTab(self.messages_panel, "Messages")

        translation_page = QWidget(results)
        translation_layout = QVBoxLayout(translation_page)
        translation_controls = QHBoxLayout()
        self.translation_target_selector = QComboBox(translation_page)
        self.translation_target_selector.setObjectName("translation_target_selector")
        self.translation_target_selector.setToolTip(
            "Choose the SQL dialect rendered in the Translation tab."
        )
        display_names = {dialect: label for label, dialect in DIALECT_MAPPING.items()}
        for dialect in sorted(DIALECT_MODULE_NAMES):
            self.translation_target_selector.addItem(
                display_names.get(dialect, dialect.title()), dialect
            )
        spark_index = self.translation_target_selector.findData("spark")
        self.translation_target_selector.setCurrentIndex(max(spark_index, 0))
        translation_target_label = QLabel("Translation target", translation_page)
        translation_target_label.setObjectName("translation_target_selector_label")
        translation_target_label.setToolTip(self.translation_target_selector.toolTip())
        translation_target_label.setBuddy(self.translation_target_selector)
        translation_controls.addWidget(translation_target_label)
        translation_controls.addWidget(self.translation_target_selector)
        translation_layout.addLayout(translation_controls)
        self.translation_panel = TranslationPanel(translation_page)
        self.translation_panel.setObjectName("translation_panel")
        translation_layout.addWidget(self.translation_panel)
        self.translation_target_selector.currentTextChanged.connect(self._refresh_translation)
        self.input_dialect_selector.currentTextChanged.connect(self._refresh_translation)
        editor.textChanged.connect(self._refresh_translation)
        editor.textChanged.connect(self._update_catalog_affordances)
        results.addTab(translation_page, "Translation")

        self.empty_catalog_banner = QLabel("Please add a dataset to begin.", results)
        self.empty_catalog_banner.setObjectName("empty_catalog_banner")
        results_layout.insertWidget(0, self.empty_catalog_banner)
        self.empty_result_banner = QLabel(results)
        self.empty_result_banner.setObjectName("empty_result_banner")
        self.empty_result_banner.setVisible(False)
        results_layout.insertWidget(1, self.empty_result_banner)

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

    def _on_apply_query_order(self, column_name: str, direction: str) -> None:
        if not self.result_table_view.has_result():
            return
        current_sql = self.editor.text()
        if not current_sql.strip():
            return
        ordered_sql = build_order_by_sql(current_sql, column_name, direction)
        self.editor.setText(ordered_sql)
        self._on_run_triggered()

    def _dispatch_focused_edit_action(self, operation: str) -> None:
        """Invoke an edit operation on the focused widget or one of its parents."""
        widget = QApplication.focusWidget()
        while widget is not None:
            if operation == "copy" and isinstance(widget, ResultTableView):
                widget.copy_selection()
                return

            method = getattr(widget, operation, None)
            if callable(method):
                method()
                return
            widget = widget.parentWidget()

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        assert menu_bar is not None
        file_menu = cast(QMenu, menu_bar.addMenu("&File"))
        file_menu.setObjectName("file_menu")
        file_menu.addAction(self.desktop_actions.add_datasets)
        file_menu.addSeparator()
        self.quit_action = QAction("Quit", self)
        self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)
        file_menu.addAction(self.quit_action)

        edit_menu = cast(QMenu, menu_bar.addMenu("&Edit"))
        edit_menu.setObjectName("edit_menu")
        undo, redo, _cut, _copy, _paste, toggle_comment = self.editor.edit_actions
        edit_menu.addAction(undo)
        edit_menu.addAction(redo)
        edit_menu.addSeparator()

        self.cut_action = QAction("Cut", self)
        self.cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.paste_action = QAction("Paste", self)
        self.paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self.select_all_action = QAction("Select All", self)
        self.select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        for action, operation in (
            (self.cut_action, "cut"),
            (self.copy_action, "copy"),
            (self.paste_action, "paste"),
            (self.select_all_action, "selectAll"),
        ):
            action.triggered.connect(
                lambda _checked=False, operation=operation: self._dispatch_focused_edit_action(
                    operation
                )
            )
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        self.find_replace_action = QAction("Find / Replace…", self)
        self.find_replace_action.setShortcut(QKeySequence("Ctrl+F"))
        self.find_replace_action.triggered.connect(self._show_find_replace)
        edit_menu.addAction(self.select_all_action)
        edit_menu.addAction(self.find_replace_action)
        edit_menu.addSeparator()
        edit_menu.addAction(toggle_comment)
        edit_menu.addSeparator()
        edit_menu.addAction(self.desktop_actions.clear_history)

        query_menu = cast(QMenu, menu_bar.addMenu("&Query"))
        query_menu.setObjectName("query_menu")
        query_menu.addAction(self.desktop_actions.run)
        query_menu.addAction(self.desktop_actions.cancel)
        query_menu.addAction(self.desktop_actions.format_sql)
        query_menu.addAction(self.desktop_actions.show_completion)
        query_menu.addSeparator()
        query_menu.addAction(self.desktop_actions.export_preview)
        query_menu.addAction(self.desktop_actions.export_full)
        query_menu.addAction(self.desktop_actions.export_selection)

        view_menu = cast(QMenu, menu_bar.addMenu("&View"))
        view_menu.setObjectName("view_menu")
        for dock in (
            self._catalog_dock_widget,
            self._schema_dock_widget,
            self._history_dock_widget,
        ):
            view_menu.addAction(dock.toggleViewAction())
        view_menu.addSeparator()
        view_menu.addAction(self.desktop_actions.reset_layout)
        view_menu.addAction(self.clear_preview_filter_action)
        self.show_hidden_files_action = QAction("Show Hidden Files", self)
        self.show_hidden_files_action.setCheckable(True)
        view_menu.addAction(self.show_hidden_files_action)
        self.preferences_action = QAction("Preferences…", self)
        self.preferences_action.triggered.connect(self._show_preferences)
        view_menu.addAction(self.preferences_action)

        help_menu = cast(QMenu, menu_bar.addMenu("&Help"))
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
            f"{build_identifier()}\n\nWherewolf is licensed under GPL-3.0-only.",
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
        self._settings_service.save_profile_on_load(dialog.profile_on_load.isChecked())
        self._settings_service.save_profile_max_bytes(dialog.profile_max_bytes.value())
        self.editor.set_theme(dialog.editor_theme_selector.currentText())
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
        self.query_controller.cancel()
        self.export_controller.cancel()
        self._elapsed_timer.stop()
        self._query_started_at = None
        shutdown_timed_out = False
        for worker in list(self._schema_workers):
            if worker.isRunning():
                worker.quit()
                if not worker.wait(5000):
                    shutdown_timed_out = True
        self._schema_workers.clear()

        for worker in list(self._profile_workers):
            if worker.isRunning():
                worker.quit()
                if not worker.wait(5000):
                    shutdown_timed_out = True
        self._profile_workers.clear()

        if self.query_controller.shutdown() is False:
            shutdown_timed_out = True
        if self.export_controller.shutdown() is False:
            shutdown_timed_out = True
        if shutdown_timed_out:
            self._show_status("Shutdown timed out waiting for background workers.")

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
