"""Widget for displaying schema columns, data types, inspection states, and errors."""

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._entry: CatalogEntry | None = None
        self._schema_result: SchemaResult | None = None
        self._profile_result: ProfileResult | None = None
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
        self._table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table_widget.setAlternatingRowColors(True)
        self._table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
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
        self._profile_result = result
        self._update_view()

    def _request_profile(self) -> None:
        if self._entry is not None:
            self.profile_requested.emit(self._entry)

    def is_pending(self) -> bool:
        """Return True if schema inspection is currently pending."""
        if self._schema_result is not None:
            return self._schema_result.columns is None and self._schema_result.error_message is None
        if self._entry is not None:
            return self._entry.schema is None and self._entry.schema_error is None
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

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        self.emit_selected_columns_insert()

    def _on_dataset_selected(self, alias: str) -> None:
        self.set_entry(self._entries_by_alias.get(alias))

    def _update_view(self) -> None:
        columns: tuple[ColumnSchema, ...] | None = None
        profiles: tuple[ColumnProfile, ...] | None = None
        error_msg: str | None = None
        alias = self._entry.alias if self._entry is not None else None

        if self._schema_result is not None:
            columns = self._schema_result.columns
            error_msg = self._schema_result.error_message
        elif self._entry is not None:
            columns = self._entry.schema
            error_msg = self._entry.schema_error
            profiles = self._entry.profile
        if self._profile_result is not None:
            profiles = self._profile_result.profiles
            if self._profile_result.error_message is not None:
                error_msg = self._profile_result.error_message

        if error_msg is not None:
            prefix = f"{alias} — " if alias is not None else ""
            self._status_label.setText(f"{prefix}Schema error: {error_msg}")
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
            if len(columns) == 0:
                prefix = f"{alias} — " if alias is not None else ""
                self._status_label.setText(f"{prefix}No columns found in table")
                self._status_label.show()
            else:
                if alias is None:
                    self._status_label.setText(f"Schema ({len(columns)} columns):")
                else:
                    assert self._entry is not None
                    self._status_label.setText(
                        f"{alias} — {self._entry.path} ({self._entry.source_format.value}) — {len(columns)} columns"
                    )
                    if self._entry.profile_skipped_reason is not None:
                        self._status_label.setText(
                            f"{self._status_label.text()} — {self._entry.profile_skipped_reason}"
                        )
                    if self._entry.profile_stale:
                        self._status_label.setText(
                            f"{self._status_label.text()} — Profile is stale; re-profile this source."
                        )
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
                        str(profile.avg) if profile and profile.avg is not None else "",
                    ),
                    start=4,
                ):
                    self._table_widget.setItem(r, index, QTableWidgetItem(value))
