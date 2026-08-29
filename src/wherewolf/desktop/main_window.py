"""Main PyQt6 window for the desktop shell."""

from __future__ import annotations

import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from importlib.metadata import version
from pathlib import Path
from typing import Any, Final, Protocol, cast
from uuid import UUID, uuid4

from PyQt6.QtCore import QByteArray, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QFontMetrics,
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
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
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
from wherewolf.desktop.page_controller import PageController
from wherewolf.desktop.query_controller import QueryController
from wherewolf.desktop.row_count_controller import RowCountController
from wherewolf.desktop.spark_metadata_controller import SparkMetadataController
from wherewolf.desktop.theming import PROGRAM_THEME_NAMES, apply_program_theme
from wherewolf.desktop.widgets import CatalogDock, HistoryDock, SavedQueriesDock, SqlEditor
from wherewolf.desktop.widgets.cell_inspector_window import CellInspectorWindow
from wherewolf.desktop.widgets.messages_panel import MessagesPanel
from wherewolf.desktop.widgets.result_table_view import ResultTableView
from wherewolf.desktop.widgets.schema_panel import SchemaPanel
from wherewolf.desktop.widgets.translation_panel import TranslationPanel
from wherewolf.desktop.widgets.value_counts_window import ValueCountsWindow
from wherewolf.desktop.workers import ProfileWorker, SchemaWorker
from wherewolf.desktop.workers.value_counts_worker import ValueCountsRegistry
from wherewolf.domain import (
    CatalogBinding,
    EngineKind,
    ExecutionRequest,
    ExecutionStatus,
    PageResult,
    ProfileResult,
    QueryResult,
    RowCountResult,
    SchemaResult,
    SelectionStatistics,
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
    StatementService,
    serialise_history_records_to_sql,
    write_atomically,
)
from wherewolf.services.execution_diagnostics import parse_duckdb_error_location
from wherewolf.services.identifier_quoting import quote_identifier
from wherewolf.services.order_by_builder import build_order_by_sql
from wherewolf.services.preview_export import write_selection
from wherewolf.services.query_parameters import (
    bind_dataset_tokens,
    bind_parameters,
    contains_dataset_token,
    extract_parameters,
)
from wherewolf.services.result_pagination import has_top_level_order_by
from wherewolf.services.text_case import TEXT_CASE_TRANSFORMS
from wherewolf.storage.catalog import CatalogStore
from wherewolf.storage.history import HistoryManager
from wherewolf.storage.saved_queries import SavedQuery, SavedQueryDirectory

SQL_DIALECT_REFERENCE_URLS: Final = {
    "DuckDB": "https://duckdb.org/docs/stable/sql/introduction",
    "PostgreSQL": "https://www.postgresql.org/docs/current/sql.html",
    "Oracle": "https://docs.oracle.com/en/database/oracle/oracle-database/23/sqlrf/SQL-Statements.html",
    "MySQL": "https://dev.mysql.com/doc/refman/8.4/en/sql-statements.html",
    "Microsoft T-SQL": "https://learn.microsoft.com/en-us/sql/t-sql/language-reference",
    "SQLite": "https://www.sqlite.org/lang.html",
    "Spark SQL": "https://spark.apache.org/docs/latest/sql-ref.html",
}

_FORMAT_TEXT_SHORTCUTS: dict[str, tuple[str, ...]] = {
    "lowercase": ("Ctrl+Shift+Y", "Ctrl+U"),
    "UPPERCASE": ("Ctrl+Shift+X", "Ctrl+Shift+U"),
    "Title Case": ("Ctrl+Shift+C",),
    "camelCase": ("Ctrl+Shift+M",),
    "snake_case": ("Ctrl+Shift+N",),
    "kebab-case": ("Ctrl+Shift+K",),
}


@dataclass
class _EditorTabState:
    """State that belongs to one SQL editor tab rather than the whole window."""

    path: Path | None = None
    last_saved_text: str | None = ""
    last_request: ExecutionRequest | None = None
    last_result: QueryResult | None = None
    result_origin: str | None = None
    row_count_request_id: UUID | None = None
    row_count_status: str = "idle"
    row_count_message: str | None = None
    page_index: int = 0
    page_has_next: bool = False
    page_loading: bool = False
    page_error: str | None = None
    page_has_stable_order: bool = False
    page_pending_index: int | None = None
    navigation_id: UUID = field(default_factory=uuid4)


class _RowCountController(Protocol):
    result_ready: Any

    @property
    def counting(self) -> bool: ...

    def count(self, request: ExecutionRequest) -> bool: ...

    def cancel(self) -> bool: ...

    def shutdown(self) -> bool: ...


class _PageController(Protocol):
    result_ready: Any

    @property
    def fetching(self) -> bool: ...

    def fetch(self, request: ExecutionRequest, page_index: int) -> bool: ...

    def cancel(self) -> bool: ...

    def shutdown(self) -> bool: ...


class _SparkMetadataController(Protocol):
    status_changed: Any

    def ensure_started(self) -> bool: ...

    def shutdown(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class _RequestOrigin:
    editor: SqlEditor
    result_origin: str
    editor_state_id: UUID
    document_snapshot: str
    fragment_start_codepoint_offset: int | None


@dataclass(frozen=True, slots=True)
class DiagnosticNavigationTarget:
    editor_state_id: UUID
    diagnostic: SqlDiagnostic
    document_snapshot: str


def _scintilla_byte_offset_to_codepoint_offset(document: str, byte_offset: int) -> int | None:
    """Convert a QScintilla UTF-8 byte position only when it is a character boundary."""
    if byte_offset < 0:
        return None
    document_bytes = document.encode("utf-8")
    if byte_offset > len(document_bytes):
        return None
    try:
        return len(document_bytes[:byte_offset].decode("utf-8"))
    except UnicodeDecodeError:
        return None


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
        self.find_next_button.clicked.connect(self._find_next)
        self.replace_next_button.clicked.connect(self._replace_next)
        self.replace_all_button.clicked.connect(self._replace_all)

    def set_editor(self, editor: SqlEditor) -> None:
        self._editor = editor

    def _find_next(self) -> None:
        self._editor.find_text(self.find_input.text())

    def _replace_next(self) -> None:
        self._editor.replace_next(self.find_input.text(), self.replace_input.text())

    def _replace_all(self) -> None:
        self._editor.replace_all(self.find_input.text(), self.replace_input.text())


class PreferencesDialog(QDialog):
    """Persisted desktop editor/completion preferences."""

    def __init__(
        self,
        settings_service: SettingsService,
        file_dialog_service: FileDialogService,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self._file_dialog_service = file_dialog_service
        layout = QFormLayout(self)
        self.saved_query_directory = QLineEdit(self)
        self.saved_query_directory.setObjectName("saved_query_directory")
        self.saved_query_directory.setText(str(settings_service.restore_saved_query_directory()))
        self.browse_saved_query_directory = QPushButton("Browse…", self)
        self.browse_saved_query_directory.setObjectName("browse_saved_query_directory")
        self.browse_saved_query_directory.clicked.connect(self._choose_saved_query_directory)
        directory_row = QWidget(self)
        directory_layout = QHBoxLayout(directory_row)
        directory_layout.setContentsMargins(0, 0, 0, 0)
        directory_layout.addWidget(self.saved_query_directory)
        directory_layout.addWidget(self.browse_saved_query_directory)
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
        self.auto_size_columns = QCheckBox("Auto-size result columns", self)
        self.auto_size_columns.setChecked(settings_service.restore_auto_size_columns())
        self.auto_size_max_width = QSpinBox(self)
        self.auto_size_max_width.setRange(50, 2000)
        self.auto_size_max_width.setValue(settings_service.restore_auto_size_max_width())
        self.editor_theme_selector = QComboBox(self)
        self.editor_theme_selector.setObjectName("editor_theme_selector")
        self.editor_theme_selector.addItems(SqlEditor.THEME_NAMES)
        self.editor_theme_selector.setCurrentText(settings_service.restore_editor_theme())
        self.program_theme_selector = QComboBox(self)
        self.program_theme_selector.setObjectName("program_theme_selector")
        self.program_theme_selector.addItems(PROGRAM_THEME_NAMES)
        self.program_theme_selector.setCurrentText(settings_service.restore_program_theme())
        layout.addRow("Saved query folder", directory_row)
        layout.addRow("Editor font size", self.font_size)
        layout.addRow(self.completion_enabled)
        layout.addRow("Completion threshold", self.completion_threshold)
        layout.addRow(self.profile_on_load)
        layout.addRow("Profile size limit (bytes)", self.profile_max_bytes)
        layout.addRow(self.auto_size_columns)
        layout.addRow("Maximum result column width (px)", self.auto_size_max_width)
        layout.addRow("Editor theme", self.editor_theme_selector)
        layout.addRow("Program theme", self.program_theme_selector)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _choose_saved_query_directory(self) -> None:
        current = self.saved_query_directory.text().strip()
        chosen = self._file_dialog_service.choose_directory(
            Path(current) if current else None, self
        )
        if chosen is not None:
            self.saved_query_directory.setText(str(chosen))


class ExportOptionsDialog(QDialog):
    """Modal format and result-scope selection for the results-page Export button."""

    def __init__(self, settings_service: SettingsService, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Options")
        layout = QFormLayout(self)
        self.format_selector = QComboBox(self)
        self.format_selector.setObjectName("export_format_selector")
        for label, export_format in (
            ("CSV", ExportFormat.CSV),
            ("Excel", ExportFormat.XLSX),
            ("Parquet", ExportFormat.PARQUET),
        ):
            self.format_selector.addItem(label, export_format)
        format_index = self.format_selector.findData(
            self._parse_export_format(settings_service.restore_export_format())
        )
        self.format_selector.setCurrentIndex(max(format_index, 0))

        self.scope_selector = QComboBox(self)
        self.scope_selector.setObjectName("export_scope_selector")
        self.scope_selector.addItem("Preview", "preview")
        self.scope_selector.addItem("Full results", "full")
        self.scope_selector.addItem("Selection", "selection")
        scope_index = self.scope_selector.findData(settings_service.restore_export_scope())
        self.scope_selector.setCurrentIndex(max(scope_index, 0))

        layout.addRow("Export format", self.format_selector)
        layout.addRow("Export scope", self.scope_selector)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @staticmethod
    def _parse_export_format(value: str) -> ExportFormat:
        try:
            return ExportFormat(value)
        except ValueError:
            return ExportFormat.CSV


class MainWindow(QMainWindow):
    """A stable, testable application shell for desktop migration phase 3."""

    LAYOUT_SCHEMA_VERSION: Final = 3

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
        row_count_controller: _RowCountController | None = None,
        page_controller: _PageController | None = None,
        history_manager: HistoryManager | None = None,
        catalog_store: CatalogStore | None = None,
        saved_query_library: SavedQueryDirectory | None = None,
        spark_metadata_controller: _SparkMetadataController | None = None,
    ) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._settings_service = settings_service or SettingsService()
        self._catalog_store = catalog_store or CatalogStore()
        restored_entries = tuple(
            replace(entry, unavailable=not entry.path.exists())
            for entry in self._catalog_store.load()
        )
        self._catalog_service = catalog_service or CatalogService(restored_entries)
        self._last_persisted_catalog = self._catalog_projection()
        self._catalog_persistence_error: str | None = None
        self._catalog_persistence_listener = self._persist_catalog
        self._catalog_service.subscribe(self._catalog_persistence_listener)
        self._file_dialog_service = file_dialog_service or QtFileDialogService()
        self._engine_registry = engine_registry or EngineRegistry()
        self.desktop_actions = actions or build_actions(self)
        self.query_controller = query_controller or QueryController(
            engine_registry=self._engine_registry, parent=self
        )
        self.export_controller = export_controller or ExportController(
            self._engine_registry, parent=self
        )
        self.row_count_controller: _RowCountController = row_count_controller or RowCountController(
            self._engine_registry, parent=self
        )
        self.page_controller: _PageController = page_controller or PageController(
            self._engine_registry, parent=self
        )
        self._last_request: ExecutionRequest | None = None
        self._last_result: QueryResult | None = None
        self.history_manager = history_manager or HistoryManager()
        self.saved_query_library = saved_query_library or SavedQueryDirectory(
            self._settings_service.restore_saved_query_directory()
        )
        self._editor_states: dict[SqlEditor, _EditorTabState] = {}
        self._result_origin_by_request_id: dict[object, _RequestOrigin] = {}
        self._schema_workers: list[SchemaWorker] = []
        self._profile_workers: list[ProfileWorker] = []
        self._value_counts_windows: list[ValueCountsWindow] = []
        self._cell_inspector_windows: list[CellInspectorWindow] = []

        self.main_toolbar = self._build_toolbar()
        self.query_controls_toolbar = self._build_query_controls_toolbar()
        self._catalog_dock_widget = self._build_catalog_dock()
        self.dataset_catalog_dock = self._catalog_dock_widget
        self._schema_dock_widget = self._build_schema_dock()
        self._history_dock_widget = self._build_history_dock()
        self._saved_queries_dock_widget = self._build_saved_queries_dock()
        self._central_splitter = self._build_central_area()
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_elapsed_status)
        self._query_started_at: float | None = None
        self._query_status = ExecutionStatus.IDLE
        self._spark_metadata_controller = spark_metadata_controller or SparkMetadataController(
            parent=self
        )
        self._spark_metadata_controller.status_changed.connect(self._on_spark_metadata_status)

        self.setCentralWidget(self._central_splitter)
        self._update_window_title()
        self._build_menus()
        self._connect_actions()
        self._restore_state()
        self._on_completion_engine_changed()
        self._queue_restored_catalog_work()
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
    def saved_queries_dock(self) -> SavedQueriesDock:
        widget = self._saved_queries_dock_widget.widget()
        assert isinstance(widget, SavedQueriesDock)
        return widget

    @property
    def editor(self) -> SqlEditor:
        """Return the active editor for compatibility with existing callers."""
        editor = self.current_editor
        assert editor is not None
        return editor

    @property
    def current_editor(self) -> SqlEditor | None:
        """Return the active SQL editor, or ``None`` when all tabs are closed."""
        editor_tabs = getattr(self, "editor_tabs", None)
        if not isinstance(editor_tabs, QTabWidget):
            return None
        widget = editor_tabs.currentWidget()
        return widget if isinstance(widget, SqlEditor) else None

    def _current_editor_state(self) -> _EditorTabState | None:
        editor = self.current_editor
        return self._editor_states.get(editor) if editor is not None else None

    @property
    def _current_sql_path(self) -> Path | None:
        state = self._current_editor_state()
        return state.path if state is not None else None

    @_current_sql_path.setter
    def _current_sql_path(self, path: Path | None) -> None:
        state = self._current_editor_state()
        if state is not None:
            state.path = path

    @property
    def _last_saved_sql_text(self) -> str | None:
        state = self._current_editor_state()
        return state.last_saved_text if state is not None else ""

    @_last_saved_sql_text.setter
    def _last_saved_sql_text(self, text: str) -> None:
        state = self._current_editor_state()
        if state is not None:
            state.last_saved_text = text

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
            self.engine_selector.addItem(label, descriptor.kind)
            item = model.item(self.engine_selector.count() - 1)
            assert item is not None
            item.setEnabled(descriptor.available)
            if not descriptor.available:
                assert descriptor.unavailable_reason is not None
                item.setData(
                    f"{label} is unavailable: {descriptor.unavailable_reason}",
                    Qt.ItemDataRole.ToolTipRole,
                )
        self._set_selector_natural_width(self.engine_selector)
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
        self._set_selector_natural_width(self.input_dialect_selector)
        self._add_labelled_control(
            controls_layout,
            "Input dialect",
            self.input_dialect_selector,
            "Choose the SQL dialect you are writing; it is transpiled to the execution engine.",
        )
        self._preview_limit_value = self._settings_service.restore_preview_limit()
        self.preview_limit_selector = QLineEdit(toolbar)
        self.preview_limit_selector.setObjectName("preview_limit_selector")
        preview_width = QFontMetrics(self.preview_limit_selector.font()).horizontalAdvance("100000")
        self.preview_limit_selector.setMaximumWidth(preview_width + 16)
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
        controls_layout.addStretch(1)
        toolbar.addWidget(controls)
        return toolbar

    @staticmethod
    def _set_selector_natural_width(selector: QComboBox) -> None:
        selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        selector.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

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
        history_dock.history_records_selected.connect(self._save_history_records_as_sql)

        dock = QDockWidget("History", self)
        dock.setObjectName("history_dock")
        dock.setWidget(history_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        return dock

    def _build_saved_queries_dock(self) -> QDockWidget:
        saved_queries_dock = SavedQueriesDock(self.saved_query_library, self)
        saved_queries_dock.run_requested.connect(self._run_saved_query)
        saved_queries_dock.open_in_new_tab_requested.connect(self._open_saved_query_in_new_tab)
        saved_queries_dock.rename_requested.connect(self._rename_saved_query)
        saved_queries_dock.delete_requested.connect(self._delete_saved_query)
        saved_queries_dock.refresh_requested.connect(self._refresh_saved_queries)

        dock = QDockWidget("Saved Queries", self)
        dock.setObjectName("saved_queries_dock")
        dock.setWidget(saved_queries_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.tabifyDockWidget(self._history_dock_widget, dock)
        self._history_dock_widget.raise_()
        return dock

    def _build_schema_dock(self) -> QDockWidget:
        schema_panel = SchemaPanel(self)
        schema_panel.insert_columns_requested.connect(self.editor_insert_text)
        schema_panel.profile_requested.connect(
            lambda entry: self._queue_profile_work(
                CatalogBinding(entry.id, entry.alias, entry.path, entry.source_format)
            )
        )
        schema_panel.value_counts_requested.connect(self._show_value_counts)

        dock = QDockWidget("Schema", self)
        dock.setObjectName("schema_dock")
        dock.setWidget(schema_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.tabifyDockWidget(self._catalog_dock_widget, dock)
        self._catalog_dock_widget.raise_()
        return dock

    def _connect_actions(self) -> None:
        self.addAction(self.desktop_actions.new_tab)
        self.addAction(self.desktop_actions.close_tab)
        self.desktop_actions.add_datasets.triggered.connect(self._on_add_datasets)
        self.desktop_actions.new_tab.triggered.connect(self._new_editor_tab)
        self.desktop_actions.close_tab.triggered.connect(self._close_current_editor_tab)
        self.desktop_actions.open_sql.triggered.connect(self._open_sql)
        self.desktop_actions.save_sql.triggered.connect(self._save_sql)
        self.desktop_actions.save_sql_as.triggered.connect(self._save_sql_as)
        self.desktop_actions.save_current_query.triggered.connect(self._save_current_query)
        self.desktop_actions.reset_layout.triggered.connect(self._reset_layout)
        self.desktop_actions.clear_history.triggered.connect(self._clear_history)
        self.desktop_actions.run.triggered.connect(self._on_run_triggered)
        self.desktop_actions.cancel.triggered.connect(self._on_cancel_triggered)
        self.desktop_actions.format_sql.triggered.connect(self._format_current_editor)
        self.desktop_actions.show_completion.triggered.connect(self._show_current_editor_completion)
        self.desktop_actions.export_preview.triggered.connect(
            lambda: self._start_export(False, self._current_export_format())
        )
        self.desktop_actions.export_full.triggered.connect(
            lambda: self._start_export(True, self._current_export_format())
        )
        self.desktop_actions.export_selection.triggered.connect(
            lambda: self._export_selection(self._current_export_format())
        )
        self.engine_selector.currentIndexChanged.connect(self._on_completion_engine_changed)

        self.query_controller.status_changed.connect(self._on_query_status_changed)
        self.query_controller.result_ready.connect(self._on_query_result_ready)
        self.export_controller.started.connect(self._on_export_started)
        self.export_controller.result_ready.connect(self._on_export_result)
        self.row_count_controller.result_ready.connect(self._on_row_count_result_ready)
        self.page_controller.result_ready.connect(self._on_page_result_ready)

    def _on_run_triggered(self) -> None:
        editor = self.current_editor
        if editor is None:
            self._show_status("No SQL editor is open", 5000)
            return
        sql, start, _end = editor.text_to_run()
        if not sql or not sql.strip():
            self._show_status("No SQL statement to run", 5000)
            return

        self._execute_sql(sql, editor=editor, fragment_start_offset=start)

    def _execute_sql(
        self,
        sql: str,
        *,
        parameters: tuple[object, ...] = (),
        original_sql: str | None = None,
        editor: SqlEditor | None = None,
        direct_saved_query: bool = False,
        fragment_start_offset: int | None = None,
    ) -> None:
        owner = editor or self.current_editor
        if owner is None:
            self._show_status("No SQL editor is open", 5000)
            return
        original_sql = sql if original_sql is None else original_sql
        if not parameters:
            prepared = self._prompt_and_bind_parameters(original_sql)
            if prepared is None:
                return
            sql, parameters = prepared
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
                parameters=parameters,
                original_sql=original_sql,
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

        self._invalidate_active_row_count()
        self._invalidate_active_page_fetch()
        if self.query_controller.execute(request):
            result_origin = "saved-query" if direct_saved_query else "editor"
            state = self._editor_states.get(owner)
            if state is None:
                return
            document_snapshot = owner.text()
            adjusted_start = None
            if fragment_start_offset is not None and not direct_saved_query:
                codepoint_offset = _scintilla_byte_offset_to_codepoint_offset(
                    document_snapshot, fragment_start_offset
                )
                if codepoint_offset is not None:
                    adjusted_start = codepoint_offset + len(sql) - len(sql.lstrip())
            self._result_origin_by_request_id[request.request_id] = _RequestOrigin(
                editor=owner,
                result_origin=result_origin,
                editor_state_id=state.navigation_id,
                document_snapshot=document_snapshot,
                fragment_start_codepoint_offset=adjusted_start,
            )

    def _save_current_query(self, _checked: bool = False) -> None:
        del _checked
        editor = self.current_editor
        if editor is None or not editor.text().strip():
            self._show_status("No SQL statement to save", 5000)
            return
        name, accepted = QInputDialog.getText(
            self, "Save Current Query", "Name (use / for subfolders)"
        )
        if not accepted:
            return
        try:
            self.saved_query_library.save_query(name=name, sql=editor.text())
        except (ValueError, OSError) as error:
            self._show_status(f"Could not save query: {error}", 5000)
            return
        self._refresh_saved_queries()

    def _refresh_saved_queries(self) -> None:
        """Rescan the library directory and report a directory that is not readable."""
        self.saved_queries_dock.refresh()
        self._report_missing_saved_query_directory()

    def _report_missing_saved_query_directory(self) -> None:
        directory = self.saved_query_library.directory
        if not directory.is_dir():
            self._show_status(f"Saved query folder does not exist: {directory}", 5000)

    def _run_saved_query(self, query: SavedQuery) -> None:
        sql = self._bind_saved_query_dataset(query.sql)
        if sql is None:
            return
        self._execute_sql(sql, original_sql=sql, direct_saved_query=True)

    def _prompt_and_bind_parameters(self, sql: str) -> tuple[str, tuple[object, ...]] | None:
        parameter_names = extract_parameters(sql)
        values: dict[str, str] = {}
        for name in parameter_names:
            value, accepted = QInputDialog.getText(
                self,
                "Run Saved Query",
                f"Value for :{name}",
            )
            if not accepted:
                return
            values[name] = value
        try:
            executable_sql, parameters = bind_parameters(sql, values)
        except ValueError as error:
            self._show_status(f"Could not bind query parameters: {error}", 5000)
            return None
        return executable_sql, tuple(parameters)

    def _bind_saved_query_dataset(self, sql: str) -> str | None:
        """Resolve the saved-query identifier token through the current catalog aliases."""
        if not contains_dataset_token(sql):
            return sql
        aliases = tuple(entry.alias for entry in self._catalog_service.entries)
        if not aliases:
            self._show_status("Add a dataset before running this saved query", 5000)
            return None
        alias, accepted = QInputDialog.getItem(
            self,
            "Run Saved Query",
            "Dataset",
            aliases,
            0,
            False,
        )
        if not accepted:
            return None
        return bind_dataset_tokens(sql, quote_identifier(alias))

    def _open_saved_query_in_new_tab(self, query: SavedQuery) -> None:
        """Open a saved query as a file-backed tab so Save overwrites the same file."""
        editor = self._new_editor_tab()
        state = self._editor_states[editor]
        state.path = Path(query.id)
        state.last_saved_text = query.sql
        editor.setText(query.sql)
        self._update_editor_tab_label(editor)
        self._update_sql_dirty_state()
        self._update_window_title()

    def _rename_saved_query(self, query: SavedQuery) -> None:
        name, accepted = QInputDialog.getText(
            self,
            "Rename Saved Query",
            "Name (use / for subfolders)",
            text=query.name,
        )
        if not accepted:
            return
        try:
            renamed = self.saved_query_library.rename_query(query.id, name)
        except (ValueError, OSError) as error:
            self._show_status(f"Could not rename query: {error}", 5000)
            return
        if renamed is None:
            self._show_status(f"Saved query no longer exists: {query.name}", 5000)
        self._refresh_saved_queries()

    def _delete_saved_query(self, query: SavedQuery) -> None:
        confirmed = QMessageBox.question(
            self,
            "Delete Saved Query",
            f"Delete the file {query.id}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed is not QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = self.saved_query_library.delete_query(query.id)
        except OSError as error:
            self._show_status(f"Could not delete query: {error}", 5000)
            return
        if not deleted:
            self._show_status(f"Saved query no longer exists: {query.name}", 5000)
        self._refresh_saved_queries()

    def _format_current_editor(self) -> None:
        editor = self.current_editor
        if editor is not None:
            editor.format_selection_or_statement()

    def _show_current_editor_completion(self) -> None:
        editor = self.current_editor
        if editor is not None:
            editor.request_completion(forced=True)

    def _on_cancel_triggered(self) -> None:
        if self.export_controller.cancel():
            return
        if self.query_controller.cancel():
            return
        if self.page_controller.cancel():
            return
        self.row_count_controller.cancel()

    def _count_all_rows(self) -> None:
        state = self._current_editor_state()
        if not self._can_count_all_rows(state):
            return
        assert state is not None
        assert state.last_request is not None
        if self.row_count_controller.count(state.last_request):
            state.row_count_request_id = state.last_request.request_id
            state.row_count_status = "counting"
            state.row_count_message = None
            self._update_row_count_controls()

    def _invalidate_active_row_count(self) -> None:
        if not self.row_count_controller.counting:
            return
        self.row_count_controller.cancel()
        for state in self._editor_states.values():
            if state.row_count_request_id is not None:
                state.row_count_request_id = None
                state.row_count_status = "idle"
                state.row_count_message = None
        self._update_row_count_controls()

    def _invalidate_active_page_fetch(self) -> None:
        if not self.page_controller.fetching:
            return
        self.page_controller.cancel()
        for state in self._editor_states.values():
            if state.page_loading:
                state.page_loading = False
                state.page_pending_index = None
        self._update_page_controls()

    def _reset_page_state(
        self, state: _EditorTabState, result: QueryResult, request: ExecutionRequest
    ) -> None:
        state.page_index = 0
        state.page_has_next = result.status is ExecutionStatus.SUCCEEDED and result.truncated
        state.page_loading = False
        state.page_error = None
        state.page_pending_index = None
        state.page_has_stable_order = has_top_level_order_by(request.executable_sql)

    def _fetch_page(self, page_index: int) -> None:
        state = self._current_editor_state()
        if state is None or state.last_request is None or not self._can_page_results(state):
            return
        if state.page_loading or page_index < 0:
            return
        if page_index > state.page_index and not self._has_next_page(state):
            return
        request = state.last_request
        if self.page_controller.fetch(request, page_index):
            state.page_loading = True
            state.page_pending_index = page_index
            state.page_error = None
            self._update_page_controls()

    def _fetch_previous_page(self) -> None:
        state = self._current_editor_state()
        if state is not None:
            self._fetch_page(state.page_index - 1)

    def _fetch_next_page(self) -> None:
        state = self._current_editor_state()
        if state is not None:
            self._fetch_page(state.page_index + 1)

    def _on_page_result_ready(self, result: object) -> None:
        if not isinstance(result, PageResult):
            return
        for editor, state in self._editor_states.items():
            request = state.last_request
            preview = state.last_result
            pending_index = state.page_pending_index
            if (
                request is None
                or preview is None
                or not state.page_loading
                or pending_index is None
                or request.request_id != result.request_id
                or result.offset != pending_index * request.preview_limit
                or result.page_size != request.preview_limit
            ):
                continue

            state.page_loading = False
            state.page_pending_index = None
            if result.status is ExecutionStatus.SUCCEEDED and result.frame is not None:
                if result.frame.height == 0 and pending_index > state.page_index:
                    state.page_has_next = False
                    state.page_error = "The next page was empty; no further rows are available."
                else:
                    state.page_index = pending_index
                    state.page_has_next = result.has_next
                    state.page_error = None
                    state.last_result = replace(
                        preview,
                        frame=result.frame,
                        execution_seconds=result.execution_seconds,
                        preview_row_count=result.frame.height,
                        total_row_count=preview.total_row_count,
                        truncated=result.has_next,
                        completed_at=result.completed_at,
                    )
                    if editor is self.current_editor:
                        self._clear_page_local_interactions()
                        self._render_query_result(state.last_result, request, show_message=False)
                        return
            elif result.status is ExecutionStatus.CANCELLED:
                state.page_error = "Page fetch cancelled; current page remains visible."
            else:
                state.page_error = result.error_message or "Could not load page; rerun the query."

            if editor is self.current_editor:
                self._update_page_controls()
            return

    def _clear_page_local_interactions(self) -> None:
        self.preview_filter_input.clear()
        selection_model = self.result_table_view.selectionModel()
        if selection_model is not None:
            selection_model.clearSelection()
        self._set_local_sort_notice_visible(False)

    def _on_row_count_result_ready(self, result: object) -> None:
        if not isinstance(result, RowCountResult):
            return
        for editor, state in self._editor_states.items():
            request = state.last_request
            preview = state.last_result
            if (
                request is None
                or preview is None
                or state.row_count_request_id != result.request_id
                or request.request_id != result.request_id
            ):
                continue
            state.row_count_request_id = None
            updated_result: QueryResult | None = None
            if result.status is ExecutionStatus.SUCCEEDED:
                if (
                    result.total_row_count is None
                    or result.total_row_count < preview.preview_row_count
                ):
                    state.row_count_status = "failed"
                    state.row_count_message = "Count result was inconsistent; rerun the query"
                else:
                    updated_result = replace(preview, total_row_count=result.total_row_count)
                    state.last_result = updated_result
                    state.row_count_status = "complete"
                    state.row_count_message = "All rows counted."
            elif result.status is ExecutionStatus.CANCELLED:
                state.row_count_status = "cancelled"
                state.row_count_message = "Count cancelled; rerun the query"
            else:
                state.row_count_status = "failed"
                state.row_count_message = (
                    result.error_message or "Could not count rows; rerun the query"
                )
            if editor is self.current_editor:
                if updated_result is not None:
                    self._last_request = request
                    self._last_result = updated_result
                    self._set_result_summary_for(updated_result, request)
                self._update_row_count_controls()
                self._update_page_controls()
            return

    def _on_query_status_changed(self, status: ExecutionStatus) -> None:
        self._query_status = status
        if status is ExecutionStatus.RUNNING:
            self._set_result_summary("")
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
        if self._query_status is ExecutionStatus.CANCELLATION_REQUESTED:
            self._show_status(f"Cancelling... ({elapsed_seconds}s)")
        else:
            self._show_status(f"Executing query... ({elapsed_seconds}s)")

    def _on_query_result_ready(self, result: QueryResult, request: ExecutionRequest) -> None:
        origin = self._result_origin_by_request_id.pop(request.request_id, None)
        owner = origin.editor if origin is not None else self.current_editor
        result_origin = origin.result_origin if origin is not None else "editor"
        self._record_query_history(result, request)
        if owner is None:
            return
        state = self._editor_states.get(owner)
        if state is None:
            return
        if state.last_request is None or state.last_request.request_id != request.request_id:
            state.row_count_request_id = None
            state.row_count_status = "idle"
            state.row_count_message = None
        state.last_request, state.last_result = request, result
        state.result_origin = result_origin
        self._reset_page_state(state, result, request)
        if owner is self.current_editor:
            self._render_query_result(
                result,
                request,
                show_message=True,
                navigation_target=self._navigation_target_for_result(origin, request, result),
            )

    def _navigation_target_for_result(
        self,
        origin: _RequestOrigin | None,
        request: ExecutionRequest,
        result: QueryResult,
    ) -> DiagnosticNavigationTarget | None:
        if (
            origin is None
            or result.status is not ExecutionStatus.FAILED
            or origin.result_origin != "editor"
            or origin.fragment_start_codepoint_offset is None
            or request.engine is not EngineKind.DUCKDB
            or request.source_dialect.casefold() != "duckdb"
            or request.original_sql != request.executable_sql
            or request.parameters
        ):
            return None

        state = self._editor_states.get(origin.editor)
        if state is None or state.navigation_id != origin.editor_state_id:
            return None
        if origin.document_snapshot != origin.editor.text():
            return None
        if len(StatementService().split_statements(request.executable_sql)) != 1:
            return None

        location = parse_duckdb_error_location(result.error_message or "")
        if location is None:
            return None
        fragment_lines = request.executable_sql.splitlines()
        if location.line > len(fragment_lines):
            return None
        source_line = fragment_lines[location.line - 1]
        if source_line != location.source_excerpt:
            return None

        relative_offset = (
            sum(
                len(line)
                for line in request.executable_sql.splitlines(keepends=True)[: location.line - 1]
            )
            + location.column
            - 1
        )
        absolute_offset = origin.fragment_start_codepoint_offset + relative_offset
        if (
            absolute_offset < 0
            or absolute_offset >= len(origin.document_snapshot)
            or origin.document_snapshot[
                origin.fragment_start_codepoint_offset : origin.fragment_start_codepoint_offset
                + len(request.executable_sql)
            ]
            != request.executable_sql
        ):
            return None

        before_location = origin.document_snapshot[:absolute_offset]
        line_start = before_location.rfind("\n") + 1
        diagnostic = SqlDiagnostic(
            message=result.error_message or "",
            severity="error",
            start_line=before_location.count("\n") + 1,
            start_column=absolute_offset - line_start + 1,
        )
        return DiagnosticNavigationTarget(
            editor_state_id=origin.editor_state_id,
            diagnostic=diagnostic,
            document_snapshot=origin.document_snapshot,
        )

    def _on_diagnostic_activated(self, target: object) -> None:
        if not isinstance(target, DiagnosticNavigationTarget):
            return
        for editor, state in self._editor_states.items():
            if state.navigation_id != target.editor_state_id:
                continue
            if editor.text() != target.document_snapshot:
                return
            index = self.editor_tabs.indexOf(editor)
            if index < 0:
                return
            self.editor_tabs.setCurrentIndex(index)
            editor.show_diagnostic(target.diagnostic)
            return

    def _record_query_history(self, result: QueryResult, request: ExecutionRequest) -> None:
        if result.status is not ExecutionStatus.SUCCEEDED:
            return
        catalog_dict = {binding.alias: str(binding.path) for binding in request.catalog}
        self.history_manager.add_entry(
            engine=request.engine.value,
            query=request.original_sql,
            catalog=catalog_dict,
        )
        self.history_dock.refresh()

    def _render_query_result(
        self,
        result: QueryResult,
        request: ExecutionRequest,
        *,
        show_message: bool,
        navigation_target: DiagnosticNavigationTarget | None = None,
    ) -> None:
        """Render a result known to belong to the currently selected editor tab."""
        self._last_request, self._last_result = request, result
        can_export = result.status is ExecutionStatus.SUCCEEDED and result.frame is not None
        self.desktop_actions.export_preview.setEnabled(can_export)
        self.desktop_actions.export_full.setEnabled(can_export)
        self.desktop_actions.export_selection.setEnabled(can_export)
        self.export_button.setEnabled(can_export)
        if result.status is ExecutionStatus.SUCCEEDED and result.frame is not None:
            self.result_table_view.set_frame(
                result.frame,
                row_offset=self._page_row_offset(self._current_editor_state(), request),
            )
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
            self.results_tabs.setCurrentWidget(self.messages_panel)
        else:
            self.result_error_message.clear()
            self.result_error_message.setVisible(False)
        self.result_truncation_notice.setVisible(
            result.status is ExecutionStatus.SUCCEEDED and result.truncated
        )
        self._update_row_count_controls()
        self._update_page_controls()

        if show_message:
            self.messages_panel.show_query_result(result, navigation_target=navigation_target)

        engine_name = (
            "DuckDB" if request.engine is EngineKind.DUCKDB else request.engine.value.title()
        )
        if result.status is ExecutionStatus.SUCCEEDED:
            self._set_result_summary_for(result, request)

            trunc_str = " (truncated)" if result.truncated else ""
            msg = (
                f"Engine: {engine_name} | State: Succeeded | Elapsed: {result.execution_seconds:.2f}s | "
                f"Preview Rows: {result.preview_row_count}{trunc_str}"
            )
            self._show_status(msg, 10000)
        elif result.status is ExecutionStatus.FAILED:
            self._set_result_summary_for(result, request)
            self._show_status(
                f"Engine: {engine_name} | State: Failed | Elapsed: {result.execution_seconds:.2f}s | Error: {result.error_message}",
                10000,
            )
        elif result.status is ExecutionStatus.CANCELLED:
            self._set_result_summary_for(result, request)
            self._show_status(
                f"Engine: {engine_name} | State: Cancelled | Elapsed: {result.execution_seconds:.2f}s | Cancellation completed",
                10000,
            )

    def _render_current_editor_result(self) -> None:
        state = self._current_editor_state()
        if state is None or state.last_request is None or state.last_result is None:
            self._last_request = None
            self._last_result = None
            self.desktop_actions.export_preview.setEnabled(False)
            self.desktop_actions.export_full.setEnabled(False)
            self.desktop_actions.export_selection.setEnabled(False)
            self.export_button.setEnabled(False)
            self.result_table_view.set_frame(None)
            self.empty_result_banner.clear()
            self.empty_result_banner.setVisible(False)
            self.result_error_message.clear()
            self.result_error_message.setVisible(False)
            self.result_truncation_notice.setVisible(False)
            self._set_result_summary("")
            self._update_row_count_controls()
            self._update_page_controls()
            return
        self._render_query_result(state.last_result, state.last_request, show_message=False)

    def _start_export(self, full_export: bool, export_format: ExportFormat | None = None) -> None:
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
        export_format = export_format or self._current_export_format()
        destination = choose_export_path(None, export_format, self)
        if destination is not None:
            self.export_controller.export(
                self._last_request,
                self._last_result.frame,
                destination,
                export_format,
                full_export,
            )

    def _show_export_options(self) -> None:
        dialog = ExportOptionsDialog(self._settings_service, self)
        self.export_options_dialog = dialog
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        export_format = dialog.format_selector.currentData()
        scope = dialog.scope_selector.currentData()
        if not isinstance(export_format, ExportFormat) or not isinstance(scope, str):
            return
        self._settings_service.save_export_format(export_format.value)
        self._settings_service.save_export_scope(scope)
        if scope == "preview":
            self._start_export(False, export_format)
        elif scope == "full":
            self._start_export(True, export_format)
        elif scope == "selection":
            self._export_selection(export_format)

    def _current_export_format(self) -> ExportFormat:
        try:
            return ExportFormat(self._settings_service.restore_export_format())
        except ValueError:
            return ExportFormat.CSV

    def _on_preview_filter_error(self, message: str) -> None:
        self.preview_filter_error.setText(message)
        self.preview_filter_error.setVisible(bool(message))

    def _export_selection(self, export_format: ExportFormat | None = None) -> None:
        if not self.result_table_view.has_result():
            return
        frame = self.result_table_view.frame()
        selected_cells, column_order = self.result_table_view.selection_for_export()
        if not selected_cells:
            self._show_status("Select result cells to export", 5000)
            return
        choose_export_path = getattr(self._file_dialog_service, "choose_export_path", None)
        export_format = export_format or self._current_export_format()
        if choose_export_path is None:
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

    def _update_window_title(self) -> None:
        name = f" — {self._current_sql_path.name}" if self._current_sql_path else ""
        dirty_marker = " *" if self.isWindowModified() else ""
        self.setWindowTitle(f"Wherewolf {version('wherewolf')}{name}{dirty_marker}")

    def _update_sql_dirty_state(self) -> None:
        editor = self.current_editor
        baseline = self._last_saved_sql_text
        is_dirty = bool(
            editor is not None
            and self._current_sql_path is not None
            and (baseline is None or editor.text() != baseline)
        )
        self.setWindowModified(is_dirty)
        self._update_window_title()

    def _open_sql(self) -> None:
        editor = self.current_editor
        if editor is None:
            return
        path = self._file_dialog_service.choose_sql_open_path(
            self._current_sql_path.parent if self._current_sql_path else None, self
        )
        if path is None:
            return
        try:
            contents = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            self._show_status(f"Could not open SQL file: {error}")
            return
        state = self._editor_states[editor]
        is_pristine_untitled = (
            state.path is None and state.last_saved_text == "" and not editor.text()
        )
        target = editor if is_pristine_untitled else self._new_editor_tab()
        target_state = self._editor_states[target]
        target_state.path = path
        target_state.last_saved_text = contents
        target.setText(contents)
        self._update_editor_tab_label(target)
        self._update_sql_dirty_state()
        self._update_window_title()

    def _save_sql(self) -> None:
        if self.current_editor is None:
            return
        if self._current_sql_path is None:
            self._save_sql_as()
            return
        self._write_sql(self._current_sql_path)

    def _save_sql_as(self) -> None:
        editor = self.current_editor
        if editor is None:
            return
        path = self._file_dialog_service.choose_sql_save_path(
            self._current_sql_path.parent if self._current_sql_path else None, self
        )
        if path is not None and self._write_sql(path):
            self._current_sql_path = path
            self._last_saved_sql_text = editor.text()
            self._update_editor_tab_label(editor)
            self._update_sql_dirty_state()
            self._update_window_title()

    def _write_sql(self, path: Path) -> bool:
        editor = self.current_editor
        if editor is None:
            return False
        try:
            path.write_text(editor.text(), encoding="utf-8")
        except OSError as error:
            self._show_status(f"Could not save SQL file: {error}")
            return False
        self._last_saved_sql_text = editor.text()
        self._update_sql_dirty_state()
        return True

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
            for editor in self._editor_states:
                editor.set_catalog(self._catalog_service.entries)
            current_editor = self.current_editor
            if (
                was_empty_catalog
                and current_editor is not None
                and not current_editor.text().strip()
            ):
                current_editor.setText(f"SELECT * FROM {quote_identifier(first.alias)}")
            self._settings_service.save_last_dataset_directory(first.path.parent)
            for entry in result.added:
                self._queue_initial_catalog_work(entry)
            message = f"Added `{first.alias}` to catalog."
            if duplicate_message:
                message = f"{message} {duplicate_message}"
            self._show_status(self._catalog_persistence_error or message)
            self._update_catalog_affordances()
        elif duplicate_message:
            self._show_status(duplicate_message)
        if result.warnings:
            self._show_status("\n".join(sorted(set(result.warnings))))
        if self._catalog_persistence_error is not None:
            self._show_status(self._catalog_persistence_error)

    def _on_refresh_catalog_schema(self, binding: CatalogBinding) -> None:
        try:
            entry = self._catalog_service.refresh_availability(binding.entry_id)
        except KeyError:
            return
        if entry.unavailable:
            self._show_status(f"Dataset is unavailable: {entry.path}", 5000)
            return
        self._queue_initial_catalog_work(entry)

    def _queue_restored_catalog_work(self) -> None:
        for entry in self._catalog_service.entries:
            if not entry.unavailable:
                self._queue_initial_catalog_work(entry)

    def _queue_initial_catalog_work(self, entry) -> None:
        binding = CatalogBinding(entry.id, entry.alias, entry.path, entry.source_format)
        self._queue_schema_work(binding)
        if not self._settings_service.restore_profile_on_load():
            return
        try:
            source_size = entry.path.stat().st_size
        except OSError:
            return
        if source_size <= self._settings_service.restore_profile_max_bytes():
            self._queue_profile_work(binding)
        else:
            self._catalog_service.mark_profile_skipped(
                entry.id, "Profiling skipped: source exceeds the configured size limit."
            )

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
        self.schema_panel.set_profile_pending(binding.entry_id, True)
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
        worker.finished.connect(
            lambda: self.schema_panel.set_profile_pending(binding.entry_id, False)
        )
        self._profile_workers.append(worker)
        worker.start()

    def _show_value_counts(self, entry, column_name: str) -> None:
        binding = CatalogBinding(entry.id, entry.alias, entry.path, entry.source_format)
        window = ValueCountsWindow(
            binding,
            column_name,
            cast(ValueCountsRegistry, self._engine_registry),
            self,
            file_dialog_service=self._file_dialog_service,
            settings_service=self._settings_service,
        )
        self._value_counts_windows.append(window)
        window.destroyed.connect(
            lambda: (
                self._value_counts_windows.remove(window)
                if window in self._value_counts_windows
                else None
            )
        )
        window.show()

    def _show_cell_inspector(self, value: object, column_name: str) -> None:
        window = CellInspectorWindow(value, column_name, self)
        self._cell_inspector_windows.append(window)
        window.destroyed.connect(
            lambda: (
                self._cell_inspector_windows.remove(window)
                if window in self._cell_inspector_windows
                else None
            )
        )
        window.show()

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
        if (
            entry is not None
            and self.schema_panel._entry is not None
            and entry.id == self.schema_panel._entry.id
        ):
            self.schema_panel.set_entries(self._catalog_service.entries, entry.alias)
            self.schema_panel.set_profile_result(profile_result)

    def _on_schema_result(self, schema_result: SchemaResult) -> None:
        self._catalog_service.update_schema(schema_result)
        for editor in self._editor_states:
            editor.set_catalog(self._catalog_service.entries)
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

    def _new_editor_tab(self, _checked: bool = False) -> SqlEditor:
        """Create, activate, and return an independent SQL editor tab."""
        del _checked
        editor = SqlEditor(
            settings_service=self._settings_service,
            format_action=self.desktop_actions.format_sql,
            show_completion_action=self.desktop_actions.show_completion,
            bind_shared_actions=False,
            parent=self,
        )
        editor.setObjectName("query_editor")
        engine = cast(EngineKind, self.engine_selector.currentData())
        editor.set_completion_dialect(engine.value)
        editor.set_catalog(self._catalog_service.entries)
        editor.diagnostics_reported.connect(self._on_editor_diagnostics)
        editor.textChanged.connect(lambda editor=editor: self._on_editor_text_changed(editor))
        self._editor_states[editor] = _EditorTabState()
        index = self.editor_tabs.addTab(editor, "Untitled")
        self.editor_tabs.setCurrentIndex(index)
        editor.setFocus()
        return editor

    def _close_current_editor_tab(self, _checked: bool = False) -> None:
        del _checked
        index = self.editor_tabs.currentIndex()
        if index >= 0:
            self._close_editor_tab(index)

    def _close_editor_tab(self, index: int) -> None:
        """Close one tab and immediately replace the last remaining tab."""
        editor = self.editor_tabs.widget(index)
        if not isinstance(editor, SqlEditor):
            return
        state = self._editor_states.get(editor)
        if state is not None and state.row_count_request_id is not None:
            self.row_count_controller.cancel()
        if state is not None and state.page_loading:
            self.page_controller.cancel()
        self.editor_tabs.removeTab(index)
        self._editor_states.pop(editor, None)
        editor.deleteLater()
        if self.editor_tabs.count() == 0:
            self._new_editor_tab()

    def _on_editor_text_changed(self, editor: SqlEditor) -> None:
        self._update_editor_tab_label(editor)
        if editor is self.current_editor:
            self._refresh_translation()
            self._update_catalog_affordances()
            self._update_sql_dirty_state()

    def _on_editor_tab_changed(self, _index: int) -> None:
        editor = self.current_editor
        if editor is None:
            return
        self._render_current_editor_result()
        self._refresh_translation()
        self._update_catalog_affordances()
        self._update_sql_dirty_state()
        dialog = getattr(self, "find_replace_dialog", None)
        if isinstance(dialog, FindReplaceDialog):
            dialog.set_editor(editor)
        editor.setFocus()

    def _update_editor_tab_label(self, editor: SqlEditor) -> None:
        state = self._editor_states.get(editor)
        if state is None:
            return
        if state.path is not None:
            label = state.path.name
        else:
            label = next((line.strip() for line in editor.text().splitlines() if line.strip()), "")
            label = label[:30] if label else "Untitled"
        index = self.editor_tabs.indexOf(editor)
        if index >= 0:
            self.editor_tabs.setTabText(index, label)

    def _build_central_area(self) -> QSplitter:
        self.editor_tabs = QTabWidget(self)
        self.editor_tabs.setObjectName("editor_tabs")
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.setMovable(True)
        self._new_editor_tab()

        self.results_tabs = QTabWidget(self)
        self.results_tabs.setObjectName("results_tabs")
        self.result_table_view = ResultTableView(self)
        self.result_table_view.setObjectName("result_table_view")
        self.result_table_view.insert_header_requested.connect(self.editor_insert_text)
        self.result_table_view.apply_query_order_requested.connect(self._on_apply_query_order)
        self.result_table_view.local_sort_changed.connect(self._set_local_sort_notice_visible)
        self.result_table_view.frame_changed.connect(
            self.desktop_actions.export_selection.setEnabled
        )
        self.inspect_cell = QAction("Inspect Cell", self)
        self.inspect_cell.setShortcut(QKeySequence("Ctrl+I"))
        self.inspect_cell.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.inspect_cell.triggered.connect(self.result_table_view.inspect_current_cell)
        self.result_table_view.addAction(self.inspect_cell)
        self.result_table_view.inspect_cell_requested.connect(self._show_cell_inspector)
        results_page = QWidget(self.results_tabs)
        results_layout = QVBoxLayout(results_page)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.result_sort_notice = QLabel("Sorted preview only.", results_page)
        self.result_sort_notice.setObjectName("result_sort_notice")
        self.result_sort_notice.setVisible(False)
        results_layout.addWidget(self.result_sort_notice)
        self.result_summary_label = QLabel(results_page)
        self.result_summary_label.setObjectName("result_summary_label")
        self.result_summary_label.setVisible(False)
        results_layout.addWidget(self.result_summary_label)
        self.result_selection_stats_label = QLabel(results_page)
        self.result_selection_stats_label.setObjectName("result_selection_stats_label")
        self.result_selection_stats_label.setVisible(False)
        results_layout.addWidget(self.result_selection_stats_label)
        self.result_table_view.selection_stats_changed.connect(
            self._set_result_selection_statistics
        )
        self.result_truncation_notice = QLabel(
            "Preview is truncated at the selected row limit. Export Full Results for all rows.",
            results_page,
        )
        self.result_truncation_notice.setObjectName("result_truncation_notice")
        self.result_truncation_notice.setVisible(False)
        truncation_controls = QHBoxLayout()
        truncation_controls.addWidget(self.result_truncation_notice)
        self.count_all_rows_button = QPushButton("Count all rows", results_page)
        self.count_all_rows_button.setObjectName("count_all_rows_button")
        self.count_all_rows_button.setVisible(False)
        self.count_all_rows_button.clicked.connect(self._count_all_rows)
        truncation_controls.addWidget(self.count_all_rows_button)
        self.result_count_status_label = QLabel(results_page)
        self.result_count_status_label.setObjectName("result_count_status_label")
        self.result_count_status_label.setVisible(False)
        truncation_controls.addWidget(self.result_count_status_label)
        truncation_controls.addStretch()
        results_layout.addLayout(truncation_controls)
        page_controls = QHBoxLayout()
        self.previous_page_button = QPushButton("Previous", results_page)
        self.previous_page_button.setObjectName("previous_page_button")
        self.previous_page_button.setVisible(False)
        self.previous_page_button.clicked.connect(self._fetch_previous_page)
        page_controls.addWidget(self.previous_page_button)
        self.page_position_label = QLabel(results_page)
        self.page_position_label.setObjectName("page_position_label")
        self.page_position_label.setVisible(False)
        page_controls.addWidget(self.page_position_label)
        self.next_page_button = QPushButton("Next", results_page)
        self.next_page_button.setObjectName("next_page_button")
        self.next_page_button.setVisible(False)
        self.next_page_button.clicked.connect(self._fetch_next_page)
        page_controls.addWidget(self.next_page_button)
        self.page_status_label = QLabel(results_page)
        self.page_status_label.setObjectName("page_status_label")
        self.page_status_label.setWordWrap(True)
        self.page_status_label.setVisible(False)
        page_controls.addWidget(self.page_status_label)
        page_controls.addStretch()
        results_layout.addLayout(page_controls)
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

        self.export_button = QPushButton("Export", results_page)
        self.export_button.setObjectName("export_button")
        self.export_button.setToolTip("Export results using the selected format and scope.")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._show_export_options)
        export_controls.addWidget(self.export_button)

        export_controls.setStretch(1, 1)
        results_layout.addLayout(export_controls)
        self.preview_filter_error = QLabel(results_page)
        self.preview_filter_error.setObjectName("preview_filter_error")
        self.preview_filter_error.setWordWrap(True)
        self.preview_filter_error.setVisible(False)
        results_layout.addWidget(self.preview_filter_error)
        results_layout.addWidget(self.result_table_view)
        self.results_tabs.addTab(results_page, "Results")
        self.messages_panel = MessagesPanel(self)
        self.messages_panel.setObjectName("messages_panel")
        self.messages_panel.diagnostic_activated.connect(self._on_diagnostic_activated)
        self.results_tabs.addTab(self.messages_panel, "Messages")

        translation_page = QWidget(self.results_tabs)
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
        self.results_tabs.addTab(translation_page, "Translation")

        self.empty_catalog_banner = QLabel("Please add a dataset to begin.", self.results_tabs)
        self.empty_catalog_banner.setObjectName("empty_catalog_banner")
        results_layout.insertWidget(0, self.empty_catalog_banner)
        self.empty_result_banner = QLabel(self.results_tabs)
        self.empty_result_banner.setObjectName("empty_result_banner")
        self.empty_result_banner.setVisible(False)
        results_layout.insertWidget(1, self.empty_result_banner)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setObjectName("central_splitter")
        splitter.addWidget(self.editor_tabs)
        splitter.addWidget(self.results_tabs)
        self.editor_tabs.tabCloseRequested.connect(self._close_editor_tab)
        self.editor_tabs.currentChanged.connect(self._on_editor_tab_changed)
        return splitter

    def _set_local_sort_notice_visible(self, is_sorted: bool) -> None:
        self.result_sort_notice.setVisible(is_sorted)

    def _refresh_translation(self) -> None:
        editor = self.current_editor
        if editor is None:
            return
        target_dialect = self.translation_target_selector.currentData()
        if not isinstance(target_dialect, str):
            return
        source_dialect = self.input_dialect_selector.currentData()
        if not isinstance(source_dialect, str):
            return
        self.translation_panel.update_translation(
            editor.text(), source_dialect=source_dialect, target_dialect=target_dialect
        )

    def editor_insert_text(self, alias: str) -> None:
        editor = self.current_editor
        if editor is not None:
            editor.insert(alias)

    def _restore_history_query(self, record: dict) -> None:
        """Place a historical SQL statement in the editor without running it."""
        query = record.get("query")
        editor = self.current_editor
        if isinstance(query, str) and editor is not None:
            editor.set_text_undoable(query)

    def _save_history_records_as_sql(self, records: list[dict[str, object]]) -> None:
        choose_history_sql_path = getattr(
            self._file_dialog_service, "choose_history_sql_path", None
        )
        if choose_history_sql_path is None:
            self._show_status("History SQL save dialog is unavailable", 5000)
            return
        destination = choose_history_sql_path(None, self)
        if destination is None:
            return

        document = serialise_history_records_to_sql(records)

        def write_sql(path: Path) -> None:
            path.write_text(document, encoding="utf-8")

        try:
            write_atomically(destination, write_sql)
        except OSError as exc:
            self._show_status(f"Failed to save history as SQL: {exc}", 5000)
            return
        self._show_status(f"Saved history as SQL to {destination}")

    def _on_apply_query_order(self, column_name: str, direction: str) -> None:
        if not self.result_table_view.has_result():
            return
        editor = self.current_editor
        state = self._current_editor_state()
        if (
            editor is None
            or state is None
            or state.result_origin == "saved-query"
            or state.last_request is not self._last_request
            or state.last_result is not self._last_result
        ):
            self._show_status(
                "Open and run this query in an editor before applying query order.", 5000
            )
            return
        current_sql = editor.text()
        if not current_sql.strip():
            return
        ordered_sql = build_order_by_sql(current_sql, column_name, direction)
        editor.set_text_undoable(ordered_sql)
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

    def _run_current_editor_action(self, operation: str) -> None:
        editor = self.current_editor
        if editor is not None:
            getattr(editor, operation)()

    def _apply_text_case(self, transform: Callable[[str], str]) -> None:
        editor = self.current_editor
        if editor is not None:
            editor.apply_text_case(transform)

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        assert menu_bar is not None
        file_menu = cast(QMenu, menu_bar.addMenu("&File"))
        file_menu.setObjectName("file_menu")
        file_menu.addAction(self.desktop_actions.add_datasets)
        file_menu.addAction(self.desktop_actions.new_tab)
        file_menu.addAction(self.desktop_actions.close_tab)
        file_menu.addAction(self.desktop_actions.open_sql)
        file_menu.addAction(self.desktop_actions.save_sql)
        file_menu.addAction(self.desktop_actions.save_sql_as)
        file_menu.addAction(self.desktop_actions.save_current_query)
        file_menu.addSeparator()
        self.quit_action = QAction("Quit", self)
        self.quit_action.setShortcuts(
            [QKeySequence("Ctrl+Q"), QKeySequence(QKeySequence.StandardKey.Quit)]
        )
        self.quit_action.triggered.connect(self.close)
        file_menu.addAction(self.quit_action)

        edit_menu = cast(QMenu, menu_bar.addMenu("&Edit"))
        edit_menu.setObjectName("edit_menu")
        editor = self.current_editor
        assert editor is not None
        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(lambda: self._run_current_editor_action("undo"))
        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(lambda: self._run_current_editor_action("redo"))
        self.toggle_comment_action = QAction("Toggle Comment", self)
        self.toggle_comment_action.setShortcut(QKeySequence("Ctrl+/"))
        # The focused SqlEditor owns the live Ctrl+/ binding; this menu entry keeps the
        # sequence for its label only, so the two do not register as an ambiguous overload.
        self.toggle_comment_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.toggle_comment_action.triggered.connect(
            lambda: self._run_current_editor_action("toggle_comment")
        )
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
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
        self.format_text_menu = cast(QMenu, edit_menu.addMenu("Format Text"))
        self.format_text_menu.setObjectName("format_text_menu")
        self.format_text_actions: dict[str, QAction] = {}
        assert _FORMAT_TEXT_SHORTCUTS.keys() == TEXT_CASE_TRANSFORMS.keys()
        for label, transform in TEXT_CASE_TRANSFORMS.items():
            action = cast(QAction, self.format_text_menu.addAction(label))
            action.setShortcuts(
                [QKeySequence(sequence) for sequence in _FORMAT_TEXT_SHORTCUTS[label]]
            )
            action.triggered.connect(
                lambda _checked=False, transform=transform: self._apply_text_case(transform)
            )
            self.format_text_actions[label] = action
        edit_menu.addSeparator()
        edit_menu.addAction(self.toggle_comment_action)
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
            self._saved_queries_dock_widget,
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
        dialect_menu = help_menu.addMenu("SQL Dialect Reference")
        assert dialect_menu is not None
        for label, url in SQL_DIALECT_REFERENCE_URLS.items():
            action = dialect_menu.addAction(label)
            assert action is not None
            action.triggered.connect(lambda _checked=False, url=url: webbrowser.open(url))
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
        editor = self.current_editor
        if editor is None:
            return
        dialog = getattr(self, "find_replace_dialog", None)
        if isinstance(dialog, FindReplaceDialog):
            dialog.set_editor(editor)
            dialog.show()
            dialog.raise_()
            return
        self.find_replace_dialog = FindReplaceDialog(editor, self)
        self.find_replace_dialog.show()

    def _show_preferences(self) -> None:
        editor = self.current_editor
        if editor is None:
            return
        self.preferences_dialog = PreferencesDialog(
            self._settings_service, self._file_dialog_service, self
        )
        original_editor_themes = {editor: editor.theme_name for editor in self._editor_states}
        original_program_theme = self._settings_service.restore_program_theme()
        self.preferences_dialog.editor_theme_selector.currentTextChanged.connect(
            self._apply_editor_theme_to_all
        )
        self.preferences_dialog.rejected.connect(
            lambda: [editor.set_theme(theme) for editor, theme in original_editor_themes.items()]
        )
        self.preferences_dialog.program_theme_selector.currentTextChanged.connect(
            self._apply_program_theme
        )
        self.preferences_dialog.rejected.connect(
            lambda: self._apply_program_theme(original_program_theme)
        )
        self.preferences_dialog.accepted.connect(self._apply_preferences)
        self.preferences_dialog.show()

    def _apply_preferences(self) -> None:
        dialog = self.preferences_dialog
        self._apply_saved_query_directory(dialog.saved_query_directory.text())
        self._settings_service.save_completion_enabled(dialog.completion_enabled.isChecked())
        self._settings_service.save_completion_threshold(dialog.completion_threshold.value())
        self._settings_service.save_profile_on_load(dialog.profile_on_load.isChecked())
        self._settings_service.save_profile_max_bytes(dialog.profile_max_bytes.value())
        self._settings_service.save_auto_size_columns(dialog.auto_size_columns.isChecked())
        self._settings_service.save_auto_size_max_width(dialog.auto_size_max_width.value())
        self.result_table_view.set_auto_size_policy(
            dialog.auto_size_columns.isChecked(), dialog.auto_size_max_width.value()
        )
        self._settings_service.save_program_theme(dialog.program_theme_selector.currentText())
        self._apply_program_theme(dialog.program_theme_selector.currentText())
        self._settings_service.save_editor_theme(dialog.editor_theme_selector.currentText())
        self._apply_editor_theme_to_all(dialog.editor_theme_selector.currentText())
        for editor in self._editor_states:
            editor.set_font_size(dialog.font_size.value())

    def _apply_saved_query_directory(self, chosen: str) -> None:
        """Repoint the saved-query library when the preferred folder changes."""
        text = chosen.strip()
        directory = Path(text) if text else self._settings_service.DEFAULT_SAVED_QUERY_DIRECTORY
        self._settings_service.save_saved_query_directory(directory)
        if directory == self.saved_query_library.directory:
            return
        self.saved_query_library.set_directory(directory)
        self._refresh_saved_queries()

    def _apply_editor_theme_to_all(self, theme: str) -> None:
        for editor in self._editor_states:
            editor.set_theme(theme)

    @staticmethod
    def _apply_program_theme(mode: str) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_program_theme(app, mode)

    def _on_editor_diagnostics(self, payload: tuple) -> None:
        for diagnostic in payload:
            self.messages_panel.add_diagnostic(diagnostic)
        if payload:
            self._show_status(payload[0].message, 5000)

    def _update_catalog_affordances(self) -> None:
        has_datasets = bool(self._catalog_service.entries)
        self.desktop_actions.run.setEnabled(has_datasets)
        self.empty_catalog_banner.setVisible(not has_datasets)

    def _catalog_projection(self) -> tuple[tuple[object, str, Path, object], ...]:
        return tuple(
            (entry.id, entry.alias, entry.path, entry.source_format)
            for entry in self._catalog_service.entries
        )

    def _persist_catalog(self) -> None:
        projection = self._catalog_projection()
        if projection == self._last_persisted_catalog:
            return
        try:
            self._catalog_store.save(self._catalog_service.entries)
        except OSError as exc:
            self._catalog_persistence_error = f"Could not save dataset catalog: {exc}"
            self.messages_panel.add_message(self._catalog_persistence_error, severity="error")
            self._show_status(self._catalog_persistence_error, 5000)
            return
        self._last_persisted_catalog = projection
        self._catalog_persistence_error = None

    def _restore_editor_tabs(self) -> None:
        tabs = self._settings_service.restore_editor_tabs()
        if not tabs:
            # `editor/text` is the workspace-persistence single-buffer key. Keep
            # it readable so upgrading users retain their draft as the first tab.
            tabs = ((self._settings_service.restore_editor_text(), None),)

        for index, (text, path) in enumerate(tabs):
            editor = self.current_editor if index == 0 else self._new_editor_tab()
            assert editor is not None
            state = self._editor_states[editor]
            state.path = path
            if path is None:
                state.last_saved_text = text
            else:
                try:
                    state.last_saved_text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    state.last_saved_text = None
            editor.setText(text)
            self._update_editor_tab_label(editor)

        active_index = min(
            self._settings_service.restore_active_editor_tab_index(),
            self.editor_tabs.count() - 1,
        )
        self.editor_tabs.setCurrentIndex(max(0, active_index))
        self._update_sql_dirty_state()

    def _restore_state(self) -> None:
        geometry = self._settings_service.restore_window_geometry()
        if geometry:
            self.restoreGeometry(QByteArray(geometry))

        if self._settings_service.restore_window_layout_version() == self.LAYOUT_SCHEMA_VERSION:
            state = self._settings_service.restore_window_state()
            if state:
                self.restoreState(QByteArray(state))
        self._settings_service.save_window_layout_version(self.LAYOUT_SCHEMA_VERSION)

        sizes = self._settings_service.restore_splitter_sizes()
        if sizes:
            self._central_splitter.setSizes(list(sizes))

        self._restore_editor_tabs()
        font_size = self._settings_service.restore_editor_font_size()
        for editor in self._editor_states:
            editor.set_font_size(font_size)
        self.result_table_view.set_auto_size_policy(
            self._settings_service.restore_auto_size_columns(),
            self._settings_service.restore_auto_size_max_width(),
        )

    def _reset_layout(self) -> None:
        """Return persistent docks and the central splitter to their default arrangement."""
        for dock, area in (
            (self._catalog_dock_widget, Qt.DockWidgetArea.LeftDockWidgetArea),
            (self._schema_dock_widget, Qt.DockWidgetArea.LeftDockWidgetArea),
            (self._history_dock_widget, Qt.DockWidgetArea.RightDockWidgetArea),
            (self._saved_queries_dock_widget, Qt.DockWidgetArea.RightDockWidgetArea),
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
        self._persist_catalog()
        listener = getattr(self, "_catalog_persistence_listener", None)
        if listener is not None:
            self._catalog_service.unsubscribe(listener)
            del self._catalog_persistence_listener
        self.query_controller.cancel()
        self.export_controller.cancel()
        self.row_count_controller.cancel()
        self.page_controller.cancel()
        self._spark_metadata_controller.shutdown()
        self._elapsed_timer.stop()
        self._query_started_at = None
        for window in list(self._value_counts_windows):
            window.close()
        self._value_counts_windows.clear()
        for window in list(self._cell_inspector_windows):
            window.close()
        self._cell_inspector_windows.clear()
        for worker in list(self._schema_workers):
            if worker.isRunning():
                worker.quit()
                worker.wait(5000)
        self._schema_workers.clear()

        for worker in list(self._profile_workers):
            if worker.isRunning():
                worker.quit()
                worker.wait(5000)
        self._profile_workers.clear()

        self.query_controller.shutdown()
        self.export_controller.shutdown()
        self.row_count_controller.shutdown()
        self.page_controller.shutdown()
        self._settings_service.save_window_geometry(self.saveGeometry().data())
        self._settings_service.save_window_state(self.saveState().data())
        self._settings_service.save_splitter_sizes(self._central_splitter.sizes())
        editor = self.current_editor
        if editor is not None:
            font = editor.font()
            if isinstance(font, QFont):
                self._settings_service.save_editor_font_size(font.pointSize())
        self._settings_service.save_editor_tabs(
            (
                (tab_editor.text(), self._editor_states[tab_editor].path)
                for index in range(self.editor_tabs.count())
                if isinstance(tab_editor := self.editor_tabs.widget(index), SqlEditor)
            ),
            self.editor_tabs.currentIndex(),
        )
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

    def _on_completion_engine_changed(self, _index: int = 0) -> None:
        """Keep all editors' completion metadata aligned with the execution engine."""

        engine = self.engine_selector.currentData()
        if not isinstance(engine, EngineKind):
            return
        for editor in self._editor_states:
            editor.set_completion_dialect(engine.value)
        if engine is EngineKind.SPARK:
            model = cast(QStandardItemModel, self.engine_selector.model())
            selected_item = model.item(self.engine_selector.currentIndex())
            if selected_item is not None and selected_item.isEnabled():
                self._spark_metadata_controller.ensure_started()

    def _on_spark_metadata_status(self, message: str) -> None:
        """Show discovery status only while Spark remains the active engine."""

        if self.engine_selector.currentData() is EngineKind.SPARK:
            self._show_status(message, 5000)

    def _set_result_summary(self, text: str) -> None:
        self.result_summary_label.setText(text)
        self.result_summary_label.setVisible(bool(text))

    def _set_result_summary_for(self, result: QueryResult, request: ExecutionRequest) -> None:
        engine_name = (
            "DuckDB" if request.engine is EngineKind.DUCKDB else request.engine.value.title()
        )
        if result.status is ExecutionStatus.SUCCEEDED:
            row_text = f"{result.preview_row_count} rows"
            if (
                result.total_row_count is not None
                and result.total_row_count != result.preview_row_count
            ):
                row_text = f"showing {result.preview_row_count} of {result.total_row_count} rows"
            summary = f"{engine_name} · {row_text} · {result.execution_seconds:.2f}s"
            if result.truncated:
                summary += f" · truncated at {result.preview_row_count} preview rows"
            self._set_result_summary(summary)
        elif result.status is ExecutionStatus.FAILED:
            self._set_result_summary(
                f"{engine_name} · failed after {result.execution_seconds:.2f}s"
            )
        elif result.status is ExecutionStatus.CANCELLED:
            self._set_result_summary(
                f"{engine_name} · cancelled after {result.execution_seconds:.2f}s"
            )

    def _can_count_all_rows(self, state: _EditorTabState | None) -> bool:
        if state is None or state.last_request is None or state.last_result is None:
            return False
        request = state.last_request
        result = state.last_result
        return (
            request.engine is EngineKind.DUCKDB
            and result.status is ExecutionStatus.SUCCEEDED
            and result.truncated
            and len(StatementService().split_statements(request.executable_sql)) == 1
        )

    def _update_row_count_controls(self) -> None:
        state = self._current_editor_state()
        if not self._can_count_all_rows(state):
            self.count_all_rows_button.setVisible(False)
            self.count_all_rows_button.setEnabled(False)
            self.result_count_status_label.clear()
            self.result_count_status_label.setVisible(False)
            return
        assert state is not None
        assert state.last_result is not None
        self.count_all_rows_button.setVisible(True)
        self.count_all_rows_button.setEnabled(
            state.row_count_status == "idle" and state.last_result.total_row_count is None
        )
        message = state.row_count_message
        if state.row_count_status == "counting":
            message = "Counting..."
        self.result_count_status_label.setText(message or "")
        self.result_count_status_label.setVisible(bool(message))

    def _can_page_results(self, state: _EditorTabState | None) -> bool:
        if state is None or state.last_request is None or state.last_result is None:
            return False
        request = state.last_request
        result = state.last_result
        return (
            request.engine is EngineKind.DUCKDB
            and result.status is ExecutionStatus.SUCCEEDED
            and len(StatementService().split_statements(request.executable_sql)) == 1
            and (state.page_index > 0 or self._has_next_page(state) or state.page_error is not None)
        )

    @staticmethod
    def _has_next_page(state: _EditorTabState) -> bool:
        assert state.last_request is not None
        assert state.last_result is not None
        total = state.last_result.total_row_count
        if not state.page_has_next:
            return False
        return total is None or (state.page_index + 1) * state.last_request.preview_limit < total

    @staticmethod
    def _page_row_offset(state: _EditorTabState | None, request: ExecutionRequest) -> int:
        """Return the absolute row index of the first row of the state's current page."""
        if state is None:
            return 0
        return state.page_index * request.preview_limit

    def _update_page_controls(self) -> None:
        state = self._current_editor_state()
        if not self._can_page_results(state):
            self.previous_page_button.setVisible(False)
            self.previous_page_button.setEnabled(False)
            self.next_page_button.setVisible(False)
            self.next_page_button.setEnabled(False)
            self.page_position_label.clear()
            self.page_position_label.setVisible(False)
            self.page_status_label.clear()
            self.page_status_label.setVisible(False)
            return
        assert state is not None
        assert state.last_request is not None
        assert state.last_result is not None
        request = state.last_request
        result = state.last_result
        page_number = state.page_index + 1
        start = self._page_row_offset(state, request) + 1
        end = start + result.preview_row_count - 1
        range_text = f"rows {start:,}-{end:,}"
        if result.total_row_count is not None:
            range_text += f" of {result.total_row_count:,}"
        status_parts = [f"{range_text} · Page {page_number}"]
        if not state.page_has_stable_order:
            status_parts.append("Page membership is not stable without a top-level ORDER BY.")
        if state.page_error:
            status_parts.append(state.page_error)

        self.previous_page_button.setVisible(True)
        self.previous_page_button.setEnabled(state.page_index > 0 and not state.page_loading)
        self.next_page_button.setVisible(True)
        self.next_page_button.setEnabled(self._has_next_page(state) and not state.page_loading)
        self.page_position_label.setText(f"Page {page_number}")
        self.page_position_label.setVisible(True)
        self.page_status_label.setText(" · ".join(status_parts))
        self.page_status_label.setVisible(True)

    def _set_result_selection_statistics(self, statistics: SelectionStatistics | None) -> None:
        if statistics is None:
            self.result_selection_stats_label.clear()
            self.result_selection_stats_label.setVisible(False)
            return
        parts = [
            f"{statistics.cell_count} cells",
            f"{statistics.distinct_count} distinct",
        ]
        if statistics.null_count:
            parts.append(f"{statistics.null_count} null")
        if statistics.numeric is not None:
            parts.extend(
                (
                    f"Sum: {statistics.numeric.total}",
                    f"Mean: {statistics.numeric.mean}",
                    f"Min: {statistics.numeric.minimum}",
                    f"Max: {statistics.numeric.maximum}",
                )
            )
        self.result_selection_stats_label.setText(" · ".join(parts))
        self.result_selection_stats_label.setVisible(True)
