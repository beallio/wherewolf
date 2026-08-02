"""Wherewolf — a local SQL workbench."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

__all__ = ["__commit__", "__version__", "build_identifier"]


def _resolve_version() -> str:
    try:
        return _dist_version("wherewolf")
    except PackageNotFoundError:  # a source tree that was never installed
        return "0+unknown"


def _resolve_commit() -> str:
    """Identify the build.

    The release version moves rarely, so two installs weeks apart report the same
    number. The commit is what actually distinguishes them.

    `_build_info` is written at build time by `hatch_build.py`, so it is present in
    installed wheels. In a source checkout it is absent and git answers instead. Neither
    path may raise: an unidentifiable build reports "unknown" rather than breaking
    startup.
    """
    try:
        from wherewolf._build_info import COMMIT

        if COMMIT:
            return COMMIT
    except ImportError:
        # A source checkout that was never built; git answers below.
        pass

    import subprocess
    from pathlib import Path

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(Path(__file__).resolve().parent),
                "rev-parse",
                "--short",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        # No git binary, or it hung. An unidentifiable build must not break startup.
        pass

    return "unknown"


__version__: str = _resolve_version()
__commit__: str = _resolve_commit()


def build_identifier() -> str:
    """One line naming exactly which build this is."""
    return f"wherewolf {__version__} (build {__commit__})"
