"""Shared QAction construction for the desktop shell."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QWidget


@dataclass(frozen=True)
class DesktopActions:
    """Typed bundle of action objects used by menu and toolbar."""

    run: QAction
    cancel: QAction
    format_sql: QAction
    add_datasets: QAction
    show_completion: QAction
    reset_layout: QAction
    clear_history: QAction
    export_preview: QAction
    export_full: QAction
    export_selection: QAction


def build_actions(parent: QWidget | None = None) -> DesktopActions:
    run = QAction("Run", parent)
    run.setShortcut(QKeySequence("Ctrl+Return"))
    run.setEnabled(True)

    cancel = QAction("Cancel", parent)
    cancel.setShortcut(QKeySequence("Ctrl+."))
    cancel.setEnabled(False)

    format_sql = QAction("Format SQL", parent)
    format_sql.setEnabled(True)
    format_sql.setShortcut(QKeySequence("Ctrl+Shift+F"))
    format_sql.setToolTip("")

    add_datasets = QAction("Add Datasets…", parent)
    add_datasets.setEnabled(True)
    add_datasets.setShortcut(QKeySequence.StandardKey.Open)
    add_datasets.setToolTip("")

    show_completion = QAction("Show Completion", parent)
    show_completion.setEnabled(True)
    show_completion.setShortcut(QKeySequence("Ctrl+Space"))

    reset_layout = QAction("Reset Layout", parent)
    reset_layout.setEnabled(True)

    clear_history = QAction("Clear History", parent)
    clear_history.setEnabled(True)

    export_preview = QAction("Export Preview…", parent)
    export_preview.setEnabled(False)
    export_full = QAction("Export Full Results…", parent)
    export_full.setEnabled(False)
    export_selection = QAction("Export Selection…", parent)
    export_selection.setEnabled(False)

    return DesktopActions(
        run=run,
        cancel=cancel,
        format_sql=format_sql,
        add_datasets=add_datasets,
        show_completion=show_completion,
        reset_layout=reset_layout,
        clear_history=clear_history,
        export_preview=export_preview,
        export_full=export_full,
        export_selection=export_selection,
    )
