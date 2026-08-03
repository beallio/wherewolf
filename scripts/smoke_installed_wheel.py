"""Build Wherewolf, install its wheel in a fresh environment, and smoke the desktop window."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = Path("/tmp/wherewolf")


def _fresh_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main() -> int:
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="installed-wheel-", dir=TEMP_ROOT))
    try:
        return _run_smoke(work_dir)
    finally:
        # Each run builds a full virtual environment (~700 MB). Without this the
        # directories accumulate: 212 of them had been left behind, filling the disk
        # until `uv build` failed with ENOSPC and three unrelated tests went red.
        shutil.rmtree(work_dir, ignore_errors=True)


def _run_smoke(work_dir: Path) -> int:
    dist_dir = work_dir / "dist"
    venv_dir = work_dir / "venv"
    smoke_home = work_dir / "home"

    subprocess.run(["uv", "build", "--out-dir", str(dist_dir)], check=True, cwd=PROJECT_ROOT)
    wheel_path = next(dist_dir.glob("wherewolf-*.whl"))
    subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(venv_dir)],
        check=True,
        cwd=PROJECT_ROOT,
    )

    fresh_python = _fresh_python(venv_dir)
    subprocess.run(
        ["uv", "pip", "install", "--python", str(fresh_python), str(wheel_path)],
        check=True,
        cwd=PROJECT_ROOT,
    )

    smoke_environment = os.environ.copy()
    smoke_environment.update(
        {
            "HOME": str(smoke_home),
            "QT_QPA_PLATFORM": "offscreen",
            "XDG_CONFIG_HOME": str(smoke_home / ".config"),
        }
    )
    for variable in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        smoke_environment.pop(variable, None)

    smoke_code = """
import importlib.util
import sys
from pathlib import Path

assert importlib.util.find_spec("pyspark") is None, "default install unexpectedly includes pyspark"
import wherewolf
from PyQt6.QtWidgets import QApplication
from wherewolf.desktop.main_window import MainWindow

assert Path(wherewolf.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
app = QApplication.instance() or QApplication([])
window = MainWindow()
window.close()
app.processEvents()
"""
    subprocess.run(
        [str(fresh_python), "-c", smoke_code],
        check=True,
        cwd=work_dir,
        env=smoke_environment,
    )

    # Printed before cleanup: the test asserts on it to prove the smoke ran in a
    # fresh environment rather than the project venv.
    print(f"Fresh virtual environment: {venv_dir}")
    print("Smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
