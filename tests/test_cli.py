import subprocess
import sys
import tomllib
from pathlib import Path

import wherewolf
import wherewolf.cli
import wherewolf.desktop.application
from wherewolf.desktop.application import main


def _project_toml_path() -> str:
    with open("pyproject.toml", "rb") as handle:
        data = tomllib.load(handle)
    return data["project"]["scripts"]["wherewolf-desktop"]


def test_console_scripts_target_desktop_entrypoints() -> None:
    assert _project_toml_path() == "wherewolf.desktop.application:main"
    with open("pyproject.toml", "rb") as handle:
        data = tomllib.load(handle)
    assert data["project"]["scripts"]["wherewolf"] == "wherewolf.cli:main"


def test_cli_delegates_to_desktop_main(monkeypatch) -> None:
    monkeypatch.setattr("wherewolf.desktop.application.main", lambda: 23)
    assert wherewolf.cli.main([]) == 23


def test_desktop_main_executes_and_returns_zero_when_exec_monkeypatched(monkeypatch) -> None:
    created = {"count": 0}

    class FakeApp:
        def __init__(self, *_args, **_kwargs):
            created["count"] += 1

        def exec(self) -> int:
            return 0

        def setStyle(self, _style) -> None:
            pass

        def setPalette(self, _palette) -> None:
            pass

        def setWindowIcon(self, _icon) -> None:
            pass

        def setDesktopFileName(self, _name: str) -> None:
            pass

    class FakeMainWindow:
        def __init__(self, *_args, **_kwargs):
            created["count"] += 1

        def show(self) -> None:
            pass

    monkeypatch.setattr(wherewolf.desktop.application, "QApplication", FakeApp)
    monkeypatch.setattr(wherewolf.desktop.application, "MainWindow", FakeMainWindow)

    result = main()

    assert result == 0
    assert created["count"] == 2


def test_importing_desktop_application_is_free_of_pyspark() -> None:
    code = (
        "import sys\n"
        "import wherewolf.desktop.application\n"
        "bad = [name for name in ('pyspark',) if name in sys.modules]\n"
        "if bad:\n"
        "    raise SystemExit('forbidden modules loaded: ' + ','.join(bad))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_cli_install_desktop_entry_command(monkeypatch, capsys) -> None:
    from wherewolf.services import desktop_entry

    calls: list[str] = []

    def fake_install():
        calls.append("install")
        return desktop_entry.InstallResult(
            desktop_entry=Path("/data/applications/wherewolf.desktop"),
            icons=(Path("/data/icons/hicolor/48x48/apps/wherewolf.png"),),
            icon_cache_refreshed=False,
        )

    monkeypatch.setattr(desktop_entry, "install_desktop_entry", fake_install)

    assert wherewolf.cli.main(["install-desktop-entry"]) == 0
    assert calls == ["install"]
    assert "wherewolf.desktop" in capsys.readouterr().out


def test_cli_remove_desktop_entry_command(monkeypatch, capsys) -> None:
    from wherewolf.services import desktop_entry

    monkeypatch.setattr(
        desktop_entry,
        "remove_desktop_entry",
        lambda: (Path("/data/applications/wherewolf.desktop"),),
    )

    assert wherewolf.cli.main(["remove-desktop-entry"]) == 0
    assert "wherewolf.desktop" in capsys.readouterr().out


def test_cli_desktop_entry_commands_do_not_launch_the_gui(monkeypatch) -> None:
    from wherewolf.services import desktop_entry

    def fail() -> int:
        raise AssertionError("desktop main must not run for an install command")

    monkeypatch.setattr("wherewolf.desktop.application.main", fail)
    monkeypatch.setattr(desktop_entry, "remove_desktop_entry", lambda: ())

    assert wherewolf.cli.main(["remove-desktop-entry"]) == 0
