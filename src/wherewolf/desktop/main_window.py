"""Main PyQt6 window for the desktop shell."""

from __future__ import annotations

from typing import cast

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QFont
from PyQt6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMenu,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
)

from wherewolf.desktop.actions import DesktopActions, build_actions
from wherewolf.desktop.dialogs import FileDialogService, QtFileDialogService
from wherewolf.desktop.query_controller import QueryController
from wherewolf.desktop.widgets import CatalogDock, SqlEditor
from wherewolf.desktop.widgets.result_table_view import ResultTableView
from wherewolf.desktop.workers import SchemaWorker
from wherewolf.domain import (
    CatalogBinding,
    EngineKind,
    ExecutionRequest,
    ExecutionStatus,
    QueryResult,
    SchemaResult,
)
from wherewolf.execution.registry import EngineRegistry
from wherewolf.services import CatalogService, ExecutionRequestBuilder, SettingsService
from wherewolf.storage.history import HistoryManager


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
        self.history_manager = history_manager or HistoryManager()
        self._schema_workers: list[SchemaWorker] = []

        self.main_toolbar = self._build_toolbar()
        self._catalog_dock_widget = self._build_catalog_dock()
        self.dataset_catalog_dock = self._catalog_dock_widget
        self._central_splitter = self._build_central_area()
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.setCentralWidget(self._central_splitter)
        self._build_menus()
        self._connect_actions()
        self._restore_state()

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

    def _connect_actions(self) -> None:
        self.desktop_actions.add_datasets.triggered.connect(self._on_add_datasets)
        self.desktop_actions.run.triggered.connect(self._on_run_triggered)
        self.desktop_actions.cancel.triggered.connect(self._on_cancel_triggered)

        self.query_controller.status_changed.connect(self._on_query_status_changed)
        self.query_controller.result_ready.connect(self._on_query_result_ready)

    def _on_run_triggered(self) -> None:
        sql, _start, _end = self.editor.text_to_run()
        if not sql or not sql.strip():
            self._show_status("No SQL statement to run", 5000)
            return

        try:
            request = ExecutionRequestBuilder.build(
                sql=sql,
                source_dialect="duckdb",
                engine=EngineKind.DUCKDB,
                catalog_service=self._catalog_service,
            )
        except Exception as exc:  # noqa: BLE001  # Request creation boundary
            self._show_status(f"Failed to prepare query: {exc}", 5000)
            return

        self.query_controller.execute(request)

    def _on_cancel_triggered(self) -> None:
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
            self.desktop_actions.run.setEnabled(True)
            self.desktop_actions.cancel.setEnabled(False)

    def _on_query_result_ready(self, result: QueryResult, request: ExecutionRequest) -> None:
        if result.status is ExecutionStatus.SUCCEEDED and result.frame is not None:
            self.result_table_view.set_frame(result.frame)
            self._results_text.setPlainText("")
        elif result.status is ExecutionStatus.FAILED:
            self.result_table_view.set_frame(None)
            self._results_text.setPlainText(f"Error ({result.error_type}): {result.error_message}")
        elif result.status is ExecutionStatus.CANCELLED:
            self.result_table_view.set_frame(None)
            self._results_text.setPlainText("Query execution cancelled.")

        if result.status is ExecutionStatus.SUCCEEDED:
            catalog_dict = {b.alias: str(b.path) for b in request.catalog}
            self.history_manager.add_entry(
                engine=request.engine.value,
                query=request.original_sql,
                catalog=catalog_dict,
            )

            trunc_str = " (truncated)" if result.truncated else ""
            msg = (
                f"Engine: DuckDB | State: Succeeded | Elapsed: {result.execution_seconds:.2f}s | "
                f"Preview Rows: {result.preview_row_count}{trunc_str}"
            )
            self._show_status(msg, 10000)

        elif result.status is ExecutionStatus.FAILED:
            msg = f"Engine: DuckDB | State: Failed | Elapsed: {result.execution_seconds:.2f}s | Error: {result.error_message}"
            self._show_status(msg, 10000)
        elif result.status is ExecutionStatus.CANCELLED:
            msg = f"Engine: DuckDB | State: Cancelled | Elapsed: {result.execution_seconds:.2f}s | Cancellation completed"
            self._show_status(msg, 10000)

    def _on_add_datasets(self) -> None:
        paths = self._file_dialog_service.choose_dataset_files(
            default_directory=self._settings_service.restore_last_dataset_directory(),
            parent=self,
        )

        if not paths:
            return

        result = self._catalog_service.add_paths(paths)
        if result.added:
            first = result.added[0]
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

    def _build_central_area(self) -> QSplitter:
        editor = SqlEditor(
            settings_service=self._settings_service,
            format_action=self.desktop_actions.format_sql,
            show_completion_action=self.desktop_actions.show_completion,
            parent=self,
        )
        editor.setObjectName("query_editor")
        editor.set_catalog(self._catalog_service.entries)
        editor.diagnostics_reported.connect(
            lambda payload: self._show_status(payload[0].message if payload else "", 5000)
        )

        results = QTabWidget(self)
        results.setObjectName("results_tabs")
        self.result_table_view = ResultTableView(self)
        self.result_table_view.setObjectName("result_table_view")
        self.result_table_view.insert_header_requested.connect(self.editor_insert_text)
        self._results_text = QTextEdit("Results pending")
        self._results_text.setObjectName("results_text")
        results.addTab(self.result_table_view, "Results")
        results.addTab(self._results_text, "Messages")

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setObjectName("central_splitter")
        splitter.addWidget(editor)
        splitter.addWidget(results)
        return splitter

    def editor_insert_text(self, alias: str) -> None:
        self.editor.insert(alias)

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        assert menu_bar is not None
        file_menu = cast(QMenu, menu_bar.addMenu("File"))
        file_menu.setObjectName("file_menu")

        edit_menu = cast(QMenu, menu_bar.addMenu("Edit"))
        edit_menu.setObjectName("edit_menu")

        query_menu = cast(QMenu, menu_bar.addMenu("Query"))
        query_menu.setObjectName("query_menu")
        query_menu.addAction(self.desktop_actions.run)
        query_menu.addAction(self.desktop_actions.cancel)
        query_menu.addAction(self.desktop_actions.format_sql)
        query_menu.addAction(self.desktop_actions.show_completion)

        view_menu = cast(QMenu, menu_bar.addMenu("View"))
        view_menu.setObjectName("view_menu")

        help_menu = cast(QMenu, menu_bar.addMenu("Help"))
        help_menu.setObjectName("help_menu")

        self.file_menu = file_menu
        self.edit_menu = edit_menu
        self.query_menu = query_menu
        self.view_menu = view_menu
        self.help_menu = help_menu

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

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        for worker in list(self._schema_workers):
            if worker.isRunning():
                worker.quit()
                worker.wait()
        self._schema_workers.clear()

        if hasattr(self, "query_controller") and self.query_controller is not None:
            for w in list(self.query_controller._workers):
                if w.isRunning():
                    w.quit()
                    w.wait()
            self.query_controller._workers.clear()

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
