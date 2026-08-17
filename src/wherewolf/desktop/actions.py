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
    new_tab: QAction
    close_tab: QAction
    open_sql: QAction
    save_sql: QAction
    save_sql_as: QAction
    show_completion: QAction
    reset_layout: QAction
    clear_history: QAction
    export_preview: QAction
    export_full: QAction
    export_selection: QAction


def build_actions(parent: QWidget | None = None) -> DesktopActions:
    run = QAction("Run", parent)
    run.setShortcut(QKeySequence("Ctrl+Return"))
    run.setToolTip("Run query (Ctrl+Return)")
    run.setEnabled(True)

    cancel = QAction("Cancel", parent)
    cancel.setShortcut(QKeySequence("Ctrl+."))
    cancel.setToolTip("Cancel query (Ctrl+.)")
    cancel.setEnabled(False)

    format_sql = QAction("Format SQL", parent)
    format_sql.setEnabled(True)
    format_sql.setShortcut(QKeySequence("Ctrl+Shift+F"))
    format_sql.setToolTip("Format SQL (Ctrl+Shift+F)")

    add_datasets = QAction("Add Datasets…", parent)
    add_datasets.setEnabled(True)
    add_datasets.setShortcut(QKeySequence.StandardKey.Open)
    add_datasets.setToolTip("Add datasets (Ctrl+O)")

    new_tab = QAction("New Tab", parent)
    new_tab.setShortcut(QKeySequence("Ctrl+T"))
    new_tab.setToolTip("Open a new SQL editor tab (Ctrl+T)")
    close_tab = QAction("Close Tab", parent)
    close_tab.setShortcut(QKeySequence("Ctrl+W"))
    close_tab.setToolTip("Close the current SQL editor tab (Ctrl+W)")

    open_sql = QAction("Open SQL…", parent)
    open_sql.setShortcut(QKeySequence("Ctrl+Shift+O"))
    open_sql.setToolTip("Open SQL file (Ctrl+Shift+O)")
    save_sql = QAction("Save SQL", parent)
    save_sql.setShortcut(QKeySequence.StandardKey.Save)
    save_sql.setToolTip("Save SQL file")
    save_sql_as = QAction("Save SQL As…", parent)
    save_sql_as.setShortcut(QKeySequence.StandardKey.SaveAs)
    save_sql_as.setToolTip("Save SQL file as")

    show_completion = QAction("Show Completion", parent)
    show_completion.setEnabled(True)
    show_completion.setShortcut(QKeySequence("Ctrl+Space"))
    show_completion.setToolTip("Show SQL completion (Ctrl+Space)")

    reset_layout = QAction("Reset Layout", parent)
    reset_layout.setEnabled(True)
    reset_layout.setToolTip("Reset the window layout")

    clear_history = QAction("Clear History", parent)
    clear_history.setEnabled(True)
    clear_history.setToolTip("Clear query history")

    export_preview = QAction("Export Preview…", parent)
    export_preview.setEnabled(False)
    export_preview.setToolTip("Export preview rows")
    export_full = QAction("Export Full Results…", parent)
    export_full.setEnabled(False)
    export_full.setToolTip("Export full query results")
    export_selection = QAction("Export Selection…", parent)
    export_selection.setEnabled(False)
    export_selection.setToolTip("Export selected result cells")

    return DesktopActions(
        run=run,
        cancel=cancel,
        format_sql=format_sql,
        add_datasets=add_datasets,
        new_tab=new_tab,
        close_tab=close_tab,
        open_sql=open_sql,
        save_sql=save_sql,
        save_sql_as=save_sql_as,
        show_completion=show_completion,
        reset_layout=reset_layout,
        clear_history=clear_history,
        export_preview=export_preview,
        export_full=export_full,
        export_selection=export_selection,
    )
