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
    format_sql.setEnabled(False)
    format_sql.setToolTip("Unavailable in Phase 3 desktop foundation")

    add_datasets = QAction("Add Datasets…", parent)
    add_datasets.setEnabled(False)
    add_datasets.setToolTip("Unavailable in Phase 3 desktop foundation")

    return DesktopActions(run=run, cancel=cancel, format_sql=format_sql, add_datasets=add_datasets)
