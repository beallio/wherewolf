import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import wherewolf
import wherewolf.cli
import wherewolf.desktop.application
from wherewolf.desktop.application import main
from wherewolf.services.export_destination import ExportFormat
from wherewolf.services.headless_query import HeadlessQueryOptions


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


def test_desktop_main_executes_and_returns_zero_when_exec_monkeypatched(monkeypatch, qapp) -> None:
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


class _FakeQueryRunner:
    def __init__(self, destination: Path, error: Exception | None = None) -> None:
        self.destination = destination
        self.error = error
        self.options: HeadlessQueryOptions | None = None

    def run(self, options: HeadlessQueryOptions) -> Path:
        self.options = options
        if self.error is not None:
            raise self.error
        return self.destination.resolve()


@pytest.mark.parametrize("export_format", tuple(ExportFormat))
def test_query_parses_typed_options_and_passes_them_to_the_runner(
    monkeypatch, tmp_path: Path, export_format: ExportFormat
) -> None:
    destination = tmp_path / f"output.{export_format.value}"
    runner = _FakeQueryRunner(destination)
    monkeypatch.setattr(wherewolf.cli, "HeadlessQueryRunner", lambda: runner, raising=False)

    result = wherewolf.cli.main(
        [
            "query",
            "SELECT * FROM sales",
            "--dataset",
            "sales=/data/sales.csv",
            "--dataset",
            "archive=/data/archive.parquet",
            "--format",
            export_format.value,
            "-o",
            str(destination),
            "--force",
        ]
    )

    assert result == 0
    assert runner.options == HeadlessQueryOptions(
        sql="SELECT * FROM sales",
        datasets=("sales=/data/sales.csv", "archive=/data/archive.parquet"),
        export_format=export_format,
        output=destination,
        force=True,
    )


def test_query_defaults_to_csv_and_accepts_long_output_option(monkeypatch, tmp_path: Path) -> None:
    destination = tmp_path / "output.anything"
    runner = _FakeQueryRunner(destination)
    monkeypatch.setattr(wherewolf.cli, "HeadlessQueryRunner", lambda: runner, raising=False)

    assert wherewolf.cli.main(["query", "SELECT 1", "--output", str(destination)]) == 0

    assert runner.options is not None
    assert runner.options.export_format is ExportFormat.CSV
    assert runner.options.datasets == ()
    assert runner.options.force is False


def test_query_success_prints_one_destination_line(monkeypatch, tmp_path: Path, capsys) -> None:
    destination = tmp_path / "out.csv"
    monkeypatch.setattr(
        wherewolf.cli,
        "HeadlessQueryRunner",
        lambda: _FakeQueryRunner(destination),
        raising=False,
    )

    assert wherewolf.cli.main(["query", "SELECT 1", "-o", str(destination)]) == 0

    captured = capsys.readouterr()
    assert captured.out == f"Wrote {destination.resolve()}\n"
    assert captured.err == ""


def test_query_failure_uses_the_stable_stderr_prefix(monkeypatch, tmp_path: Path, capsys) -> None:
    destination = tmp_path / "out.csv"
    monkeypatch.setattr(
        wherewolf.cli,
        "HeadlessQueryRunner",
        lambda: _FakeQueryRunner(destination, ValueError("invalid dataset")),
        raising=False,
    )

    assert wherewolf.cli.main(["query", "SELECT 1", "-o", str(destination)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "wherewolf query: invalid dataset\n"


@pytest.mark.parametrize(
    "argv",
    (
        ("query",),
        ("query", "SELECT 1"),
        ("query", "SELECT 1", "--format", "json", "-o", "out.csv"),
    ),
)
def test_query_syntax_errors_retain_argparse_exit_two(argv: tuple[str, ...]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        wherewolf.cli.main(argv)

    assert exc_info.value.code == 2


def test_query_subprocess_stays_free_of_qt_and_pyspark_with_unusable_qt(tmp_path: Path) -> None:
    destination = tmp_path / "constant.csv"
    code = (
        "import sys\n"
        "from wherewolf.cli import main\n"
        f"exit_code = main(['query', 'SELECT 1 AS answer', '-o', {str(destination)!r}])\n"
        "if exit_code != 0:\n"
        "    raise SystemExit(exit_code)\n"
        "forbidden = [name for name in sys.modules if name.startswith(('PyQt6', 'pyspark'))]\n"
        "if forbidden:\n"
        "    raise SystemExit('forbidden modules loaded: ' + ', '.join(forbidden))\n"
    )
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "definitely-not-a-platform"
    environment["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/nonexistent/wherewolf-qt-plugins"

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == f"Wrote {destination.resolve()}\n"
    assert result.stderr == ""
    assert destination.read_text() == "answer\n1\n"
