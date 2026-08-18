from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QStyleOptionViewItem

from wherewolf.desktop.widgets.folder_column_delegate import FolderColumnDelegate, dim_colour


def test_dim_colour_blends_toward_the_base_in_light_and_dark_themes() -> None:
    light_theme = dim_colour(QColor(20, 40, 60), QColor(220, 200, 180))
    dark_theme = dim_colour(QColor(220, 200, 180), QColor(20, 40, 60))

    for channel in ("red", "green", "blue"):
        assert 20 < getattr(light_theme, channel)() < getattr(QColor(220, 200, 180), channel)()
        assert getattr(QColor(20, 40, 60), channel)() < getattr(dark_theme, channel)() < 220


def test_folder_column_delegate_left_elides_folder_text(qtbot) -> None:
    delegate = FolderColumnDelegate()
    option = QStyleOptionViewItem()

    delegate.initStyleOption(option, QModelIndex())

    assert option.textElideMode == Qt.TextElideMode.ElideLeft
