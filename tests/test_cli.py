import subprocess
import sys
import tomllib

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
    monkeypatch.setattr(wherewolf.cli, "desktop_main", lambda: 23)
    assert wherewolf.cli.main() == 23


def test_desktop_main_executes_and_returns_zero_when_exec_monkeypatched(monkeypatch) -> None:
    created = {"count": 0}

    class FakeApp:
        def __init__(self, *_args, **_kwargs):
            created["count"] += 1

        def exec(self) -> int:
            return 0

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
