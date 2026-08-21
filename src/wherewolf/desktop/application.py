"""Desktop application entry point."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from wherewolf.desktop.app_icon import DESKTOP_FILE_NAME, load_app_icon
from wherewolf.desktop.main_window import MainWindow
from wherewolf.desktop.theming import apply_program_theme
from wherewolf.services import SettingsService


def main() -> int:
    app = getattr(QApplication, "instance", lambda: None)() or QApplication([])
    # Both, and before the first window exists: X11 and the title bar read the window
    # icon, while Wayland ignores it and resolves the desktop entry named by the app_id
    # that setDesktopFileName supplies.
    app.setWindowIcon(load_app_icon())
    app.setDesktopFileName(DESKTOP_FILE_NAME)
    settings = SettingsService()
    apply_program_theme(app, settings.restore_program_theme())
    window = MainWindow(settings_service=settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
