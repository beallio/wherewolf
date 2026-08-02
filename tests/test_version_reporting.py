"""Guards for telling one installed build from another.

`uv tool install` copies the source rather than linking it, so an install goes stale the
moment `dev` moves on. With the version pinned at 0.5.2 across every build, there was no
way to tell a fresh install from a week-old one without inspecting package internals —
which is exactly how a fixed bug looked unfixed.

The build commit is what distinguishes builds; the release version does not move often
enough to.
"""

from __future__ import annotations

import subprocess
import sys

import wherewolf
from wherewolf.cli import main


def test_package_exposes_a_version() -> None:
    assert isinstance(wherewolf.__version__, str)
    assert wherewolf.__version__, "wherewolf.__version__ must not be empty"


def test_package_exposes_a_build_commit() -> None:
    """A build identifier must exist even when git is unavailable."""
    assert isinstance(wherewolf.__commit__, str)
    assert wherewolf.__commit__, (
        "wherewolf.__commit__ must always be a string — 'unknown' when it cannot be "
        "determined, never absent"
    )


def test_version_flag_reports_version_and_commit(capsys) -> None:
    exit_code = main(["--version"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert wherewolf.__version__ in out
    assert wherewolf.__commit__ in out, (
        "the commit is the part that actually distinguishes two builds of the same "
        f"version; got: {out!r}"
    )


def test_version_flag_does_not_launch_the_gui() -> None:
    """--version must be answerable on a headless box with no Qt platform."""
    result = subprocess.run(
        [sys.executable, "-m", "wherewolf", "--version"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={"PATH": "/usr/bin:/bin", "QT_QPA_PLATFORM": "definitely-not-a-platform"},
    )

    assert result.returncode == 0, (
        f"--version must not need a display or a working Qt platform plugin.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr[-1500:]}"
    )
    assert wherewolf.__version__ in result.stdout


def test_main_without_arguments_still_launches_the_desktop_app(monkeypatch) -> None:
    """The version flag must not disturb the ordinary entry point."""
    launched: list[bool] = []

    def fake_desktop_main() -> int:
        launched.append(True)
        return 0

    monkeypatch.setattr("wherewolf.desktop.application.main", fake_desktop_main)

    assert main([]) == 0
    assert launched == [True]


def test_built_wheel_carries_the_real_commit(tmp_path) -> None:
    """The stamp must survive `uv build`, which builds the wheel from the sdist.

    The sdist is extracted into a directory with no git repository, so a hook that
    regenerates the stamp unconditionally writes "unknown" into the artifact users
    actually install — while the source tree still looks correct.
    """
    import zipfile

    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if head.returncode != 0:
        import pytest

        pytest.skip("not a git checkout")
    expected = head.stdout.strip()

    build = subprocess.run(
        ["uv", "build", "--out-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert build.returncode == 0, build.stderr[-2000:]

    wheels = list(tmp_path.glob("*.whl"))
    assert wheels, "uv build produced no wheel"

    with zipfile.ZipFile(wheels[0]) as archive:
        stamp = archive.read("wherewolf/_build_info.py").decode("utf-8")

    assert f'COMMIT = "{expected}"' in stamp, (
        f"the built wheel must carry the real commit, not a placeholder; got: {stamp!r}"
    )
