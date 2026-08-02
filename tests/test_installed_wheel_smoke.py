import subprocess
import sys
from pathlib import Path


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
