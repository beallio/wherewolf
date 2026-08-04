from PyQt6.QtWidgets import QLabel, QWidget

from wherewolf.desktop.main_window import MainWindow


def test_main_window_labels_every_query_control(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    controls = {
        "engine_selector": "Execution engine",
        "input_dialect_selector": "Input dialect",
        "preview_limit_selector": "Preview rows",
        "translation_target_selector": "Translation target",
    }

    for object_name, caption in controls.items():
        control = window.findChild(QWidget, object_name)
        label = window.findChild(QLabel, f"{object_name}_label")

        assert control is not None
        assert control.toolTip().strip()
        assert label is not None
        assert label.text() == caption
        assert label.buddy() is control
        assert not label.isHidden()
