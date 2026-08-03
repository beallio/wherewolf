import subprocess
import sys
from pathlib import Path

TEMP_ROOT = Path("/tmp/wherewolf")


def test_clean_installed_wheel_smoke_script() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/smoke_installed_wheel.py"],
        check=True,
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
    )

    assert "Smoke test passed" in result.stdout
    assert "Fresh virtual environment:" in result.stdout

    # The script builds a ~700 MB virtual environment per run. It once leaked one every
    # time, and 212 of them filled the disk until `uv build` failed with ENOSPC, turning
    # three unrelated tests red. The work directory must not survive the run.
    leaked = sorted(TEMP_ROOT.glob("installed-wheel-*"))
    assert not leaked, f"smoke script left {len(leaked)} work directories behind: {leaked[:3]}"
