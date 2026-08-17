"""Widget for displaying schema columns, data types, inspection states, and errors."""

from uuid import UUID

from PyQt6.QtCore import QItemSelectionModel, QPoint, QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wherewolf.desktop.clipboard_serializers import serialize_table_widget_to_tsv
from wherewolf.domain.models import (
    CatalogEntry,
    ColumnProfile,
    ColumnSchema,
    ProfileResult,
    SchemaResult,
)
from wherewolf.services.identifier_quoting import quote_identifier


class SchemaPanel(QWidget):
    """Displays column names and data types for catalog entries or schema inspection results.

    Signals:
        insert_columns_requested(str): Emitted when user requests inserting selected column(s) into editor.
    """

    insert_columns_requested = pyqtSignal(str)
    profile_requested = pyqtSignal(CatalogEntry)
    value_counts_requested = pyqtSignal(CatalogEntry, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._entry: CatalogEntry | None = None
        self._schema_result: SchemaResult | None = None
        self._profile_result: ProfileResult | None = None
        self._pending_profile_entry_ids: set[UUID] = set()
        self._entries_by_alias: dict[str, CatalogEntry] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.dataset_selector = QComboBox(self)
        self.dataset_selector.setObjectName("schema_dataset_selector")
        self.dataset_selector.setToolTip("Choose the dataset whose schema is displayed.")
        self.dataset_selector.currentTextChanged.connect(self._on_dataset_selected)
        layout.addWidget(self.dataset_selector)
        self.profile_button = QPushButton("Profile", self)
        self.profile_button.clicked.connect(self._request_profile)
        layout.addWidget(self.profile_button)

        self._status_label = QLabel("No table selected", self)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        self._warning_label = QLabel(self)
        self._warning_label.setObjectName("schema_warning_label")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        layout.addWidget(self._warning_label)

        self._table_widget = QTableWidget(0, 9, self)
        self._table_widget.setHorizontalHeaderLabels(
            [
                "Name",
                "Type",
                "Nullable",
                "Position",
                "Null %",
                "Distinct (approx.)",
                "Min",
                "Max",
                "Mean",
            ]
        )
        header = self._table_widget.horizontalHeader()
        if header is not None:
            header.setSectionsMovable(True)
            header.setStretchLastSection(True)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._table_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table_widget.setAlternatingRowColors(True)
        self._table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table_widget.customContextMenuRequested.connect(self._on_context_menu_requested)
        self._table_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._table_widget)

        self._update_view()

    def set_entry(self, entry: CatalogEntry | None) -> None:
        """Set the catalog entry to display."""
        self._entry = entry
        self._schema_result = None
        self._profile_result = None
        self._update_view()

    def set_entries(self, entries: tuple[CatalogEntry, ...], selected_alias: str | None) -> None:
        """Populate the dataset selector and display the requested catalog entry."""
        self._entries_by_alias = {entry.alias: entry for entry in entries}
        with QSignalBlocker(self.dataset_selector):
            self.dataset_selector.clear()
            self.dataset_selector.addItems(self._entries_by_alias)
            if selected_alias is not None:
                self.dataset_selector.setCurrentText(selected_alias)
        self.set_entry(self._entries_by_alias.get(self.dataset_selector.currentText()))

    def set_schema_result(self, result: SchemaResult) -> None:
        """Update display using a SchemaResult directly."""
        self._schema_result = result
        self._update_view()

    def set_profile_result(self, result: ProfileResult) -> None:
        if self._entry is None or self._entry.id != result.entry_id:
            return
        self._profile_result = result
        self._update_view()

    def set_profile_pending(self, entry_id: UUID, pending: bool) -> None:
        if pending:
            self._pending_profile_entry_ids.add(entry_id)
        else:
            self._pending_profile_entry_ids.discard(entry_id)
        self._update_view()

    def _request_profile(self) -> None:
        if self._entry is not None:
            self.profile_requested.emit(self._entry)

    def is_pending(self) -> bool:
        """Return True if schema inspection is currently pending."""
        if self._schema_result is not None:
            return self._schema_result.columns is None and self._schema_result.error_message is None
        if self._entry is not None:
            return (
                self._entry.schema is None
                and self._entry.schema_error is None
                or (self._entry.id in self._pending_profile_entry_ids)
            )
        return False

    def has_error(self) -> bool:
        """Return True if schema inspection failed with an error."""
        if self._schema_result is not None:
            return self._schema_result.error_message is not None
        if self._entry is not None:
            return self._entry.schema_error is not None
        return False

    def status_text(self) -> str:
        """Return the current status label text."""
        return self._status_label.text()

    def warning_text(self) -> str:
        """Return the current schema-warning text."""
        return self._warning_label.text()

    def column_count_rows(self) -> int:
        """Return the number of column rows displayed in the table."""
        return self._table_widget.rowCount()

    def cell_text(self, row: int, col: int) -> str:
        """Return text of item at row, col."""
        item = self._table_widget.item(row, col)
        return item.text() if item is not None else ""

    def get_selected_column_names(self) -> list[str]:
        """Return selected column names in display order."""
        selected_indexes = self._table_widget.selectedIndexes()
        rows = sorted({idx.row() for idx in selected_indexes})
        return [self.cell_text(r, 0) for r in rows if self.cell_text(r, 0)]

    def emit_selected_columns_insert(self) -> None:
        """Emit insert_columns_requested signal with quoted column identifiers."""
        names = self.get_selected_column_names()
        if not names:
            return
        quoted = [quote_identifier(name) for name in names]
        self.insert_columns_requested.emit(", ".join(quoted))

    def create_context_menu(self, row: int | None = None, column: int | None = None) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Copy", self.copy_selection)
        if row is not None and column is not None and self._entry is not None:
            column_item = self._table_widget.item(row, 0)
            if column_item is not None:
                menu.addAction(
                    "Value counts",
                    lambda: self.value_counts_requested.emit(self._entry, column_item.text()),
                )
        return menu

    def _on_context_menu_requested(self, pos: QPoint) -> None:
        index = self._table_widget.indexAt(pos)
        viewport = self._table_widget.viewport()
        if not index.isValid() or viewport is None:
            return
        selection_model = self._table_widget.selectionModel()
        if selection_model is None or not selection_model.isSelected(index):
            self._table_widget.setCurrentCell(
                index.row(), index.column(), QItemSelectionModel.SelectionFlag.ClearAndSelect
            )
        menu = self.create_context_menu(index.row(), index.column())
        QMenu.exec(menu, viewport.mapToGlobal(pos))

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0 is not None and a0.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()
            a0.accept()
            return
        super().keyPressEvent(a0)

    def copy_selection(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        text = serialize_table_widget_to_tsv(self._table_widget)
        if text:
            clipboard.setText(text)

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        self.emit_selected_columns_insert()

    def _on_dataset_selected(self, alias: str) -> None:
        self.set_entry(self._entries_by_alias.get(alias))

    def _update_view(self) -> None:
        columns: tuple[ColumnSchema, ...] | None = None
        profiles: tuple[ColumnProfile, ...] | None = None
        schema_error_msg: str | None = None
        profile_error_msg: str | None = None
        alias = self._entry.alias if self._entry is not None else None

        if self._schema_result is not None:
            columns = self._schema_result.columns
            schema_error_msg = self._schema_result.error_message
        elif self._entry is not None:
            columns = self._entry.schema
            schema_error_msg = self._entry.schema_error
            profiles = self._entry.profile
        if self._profile_result is not None:
            profiles = self._profile_result.profiles
            profile_error_msg = self._profile_result.error_message

        self._warning_label.clear()
        self._warning_label.hide()

        if schema_error_msg is not None:
            prefix = f"{alias} — " if alias is not None else ""
            self._status_label.setText(f"{prefix}Schema error: {schema_error_msg}")
            self._status_label.show()
            self._table_widget.setRowCount(0)
            self._table_widget.hide()
        elif columns is None:
            if self._entry is None and self._schema_result is None:
                self._status_label.setText("No table selected")
            else:
                prefix = f"{alias} — " if alias is not None else ""
                self._status_label.setText(f"{prefix}Schema inspection pending...")
            self._status_label.show()
            self._table_widget.setRowCount(0)
            self._table_widget.hide()
        else:
            warnings: list[str] = []
            if len(columns) == 0:
                prefix = f"{alias} — " if alias is not None else ""
                self._status_label.setText(f"{prefix}No columns found in table")
            else:
                if alias is None:
                    self._status_label.setText(f"Schema ({len(columns)} columns):")
                else:
                    assert self._entry is not None
                    self._status_label.setText(
                        f"{alias} — {self._entry.path.name} ({self._entry.source_format.value}) — {len(columns)} columns"
                    )
                    self._status_label.setToolTip(str(self._entry.path))
                    if self._entry.profile_skipped_reason is not None:
                        warnings.append(self._entry.profile_skipped_reason)
                    if self._entry.profile_stale:
                        warnings.append("Profile is stale; re-profile this source.")
                if profile_error_msg is not None:
                    warnings.append(f"Profiling failed: {profile_error_msg}")
                if self._is_profile_pending():
                    warnings.append("Profiling...")
                if warnings:
                    self._warning_label.setText(" — ".join(warnings))
                    self._warning_label.show()
            self._status_label.show()

            self._table_widget.show()
            self._table_widget.setRowCount(len(columns))
            for r, col in enumerate(columns):
                name_item = QTableWidgetItem(col.name)
                type_item = QTableWidgetItem(col.data_type)
                nullable_item = QTableWidgetItem(
                    "Yes" if col.nullable is True else "No" if col.nullable is False else "Unknown"
                )
                position_item = QTableWidgetItem(str(r + 1))
                profile = next((item for item in profiles or () if item.name == col.name), None)
                self._table_widget.setItem(r, 0, name_item)
                self._table_widget.setItem(r, 1, type_item)
                self._table_widget.setItem(r, 2, nullable_item)
                self._table_widget.setItem(r, 3, position_item)
                for index, value in enumerate(
                    (
                        f"{profile.null_percentage:.2f}"
                        if profile and profile.null_percentage is not None
                        else "",
                        str(profile.approx_unique)
                        if profile and profile.approx_unique is not None
                        else "",
                        profile.min if profile and profile.min is not None else "",
                        profile.max if profile and profile.max is not None else "",
                        profile.avg if profile and profile.avg is not None else "",
                    ),
                    start=4,
                ):
                    self._table_widget.setItem(r, index, QTableWidgetItem(value))

        self.profile_button.setEnabled(not self._is_profile_pending())

    def _is_profile_pending(self) -> bool:
        return self._entry is not None and self._entry.id in self._pending_profile_entry_ids
