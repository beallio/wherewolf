def test_qt_imports() -> None:
    import PyQt6
    from PyQt6 import Qsci

    assert PyQt6.__name__ == "PyQt6"
    assert Qsci is not None


def test_qt_application(qapp) -> None:
    from PyQt6 import QtCore

    assert qapp is not None
    assert QtCore.QCoreApplication.instance() is not None
    assert qapp.platformName() == "offscreen"


def test_qscintilla_widget(qtbot, qapp):
    from PyQt6 import Qsci

    editor = Qsci.QsciScintilla()
    qtbot.addWidget(editor)
    editor.setText("SELECT 1")
    assert editor.text() == "SELECT 1"
    editor.deleteLater()
    qapp.processEvents()


def test_qt_version_string() -> None:
    from PyQt6 import QtCore

    assert isinstance(QtCore.QT_VERSION_STR, str)
    assert QtCore.QT_VERSION_STR != ""
    assert QtCore.QT_VERSION_STR.startswith("6.")
