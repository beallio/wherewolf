"""Desktop application entry point."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from wherewolf.desktop.main_window import MainWindow
from wherewolf.desktop.theming import apply_program_theme
from wherewolf.services import SettingsService


def main() -> int:
    app = getattr(QApplication, "instance", lambda: None)() or QApplication([])
    settings = SettingsService()
    apply_program_theme(app, settings.restore_program_theme())
    window = MainWindow(settings_service=settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
