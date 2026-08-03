from PyQt6.QtGui import QFontMetrics

from wherewolf.desktop.main_window import MainWindow


def test_main_window_line_number_margin_fits_document_digits_after_font_change(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    editor = window.editor

    for line_count in (5, 50, 500):
        editor.setText("\n".join("SELECT 1" for _ in range(line_count)))
        required_width = QFontMetrics(editor.font()).horizontalAdvance("9" * len(str(line_count)))

        assert editor.marginWidth(0) >= required_width

    editor.set_font_size(24)
    assert editor.font().pointSize() == 24
    required_width = QFontMetrics(editor.font()).horizontalAdvance("9" * len(str(500)))

    assert editor.marginWidth(0) >= required_width
