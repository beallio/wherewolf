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

    return DesktopActions(run=run, cancel=cancel, format_sql=format_sql, add_datasets=add_datasets)
