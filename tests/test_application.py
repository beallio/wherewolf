from wherewolf.desktop import application


def test_desktop_main_applies_program_theme_before_constructing_window(monkeypatch) -> None:
    events: list[str] = []

    class FakeApp:
        def __init__(self, *_args, **_kwargs):
            events.append("app")

        def setWindowIcon(self, _icon) -> None:
            events.append("window-icon")

        def setDesktopFileName(self, name: str) -> None:
            events.extend(("desktop-file-name", name))

        def exec(self) -> int:
            events.append("exec")
            return 0

    class FakeSettings:
        def __init__(self):
            events.append("settings")

        def restore_program_theme(self) -> str:
            events.append("restore-theme")
            return "Dark"

    class FakeMainWindow:
        def __init__(self, **_kwargs):
            events.append("window")

        def show(self) -> None:
            events.append("show")

    def apply_theme(_app, mode: str) -> None:
        events.extend(("apply-theme", mode))

    monkeypatch.setattr(application, "QApplication", FakeApp)
    monkeypatch.setattr(application, "SettingsService", FakeSettings)
    monkeypatch.setattr(application, "apply_program_theme", apply_theme)
    monkeypatch.setattr(application, "MainWindow", FakeMainWindow)
    monkeypatch.setattr(application, "load_app_icon", lambda: "icon")

    assert application.main() == 0
    assert events == [
        "app",
        "window-icon",
        "desktop-file-name",
        "wherewolf",
        "settings",
        "restore-theme",
        "apply-theme",
        "Dark",
        "window",
        "show",
        "exec",
    ]
