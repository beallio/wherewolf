"""Delegate for the catalog folder column."""

from __future__ import annotations

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem


def dim_colour(text: QColor, base: QColor, factor: float = 0.55) -> QColor:
    """Blend text colour toward the background while preserving its direction."""
    return QColor(
        round(text.red() * (1 - factor) + base.red() * factor),
        round(text.green() * (1 - factor) + base.green() * factor),
        round(text.blue() * (1 - factor) + base.blue() * factor),
    )


class FolderColumnDelegate(QStyledItemDelegate):
    """Left-elide and visually de-emphasize catalog folder values."""

    def initStyleOption(self, option: QStyleOptionViewItem | None, index: QModelIndex) -> None:
        super().initStyleOption(option, index)
        if option is None:
            return
        option.textElideMode = Qt.TextElideMode.ElideLeft
        palette = option.palette
        dimmed = dim_colour(palette.text().color(), palette.base().color())
        palette.setColor(QPalette.ColorRole.Text, dimmed)
        palette.setColor(QPalette.ColorRole.WindowText, dimmed)
        option.palette = palette
