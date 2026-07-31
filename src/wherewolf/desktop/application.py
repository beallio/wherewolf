"""Desktop application entry point."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from wherewolf.desktop.main_window import MainWindow


def main() -> int:
    app = getattr(QApplication, "instance", lambda: None)() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
