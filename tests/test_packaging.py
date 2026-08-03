import subprocess
import tarfile
import zipfile
from pathlib import Path


def test_built_distributions_include_licenses_and_desktop_entry_points(tmp_path: Path) -> None:
    """Release artifacts, rather than project metadata, are the packaging contract."""
    dist_dir = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist_dir)],
        check=True,
        cwd=Path.cwd(),
    )

    wheel_path = next(dist_dir.glob("wherewolf-*.whl"))
    sdist_path = next(dist_dir.glob("wherewolf-*.tar.gz"))

    with zipfile.ZipFile(wheel_path) as wheel:
        wheel_names = wheel.namelist()
        metadata_name = next(name for name in wheel_names if name.endswith(".dist-info/METADATA"))
        entry_points_name = next(
            name for name in wheel_names if name.endswith(".dist-info/entry_points.txt")
        )
        metadata = wheel.read(metadata_name).decode("utf-8")
        entry_points = wheel.read(entry_points_name).decode("utf-8")

    assert any(name.endswith("/LICENSE") for name in wheel_names)
    assert any(name.endswith("/LICENSES/MIT-pre-0.6.txt") for name in wheel_names)
    assert "License-Expression: GPL-3.0-only" in metadata
    assert "wherewolf = wherewolf.cli:main" in entry_points
    assert "wherewolf-desktop = wherewolf.desktop.application:main" in entry_points

    with tarfile.open(sdist_path) as sdist:
        sdist_names = sdist.getnames()

    assert any(name.endswith("/LICENSE") for name in sdist_names)
    assert any(name.endswith("/LICENSES/MIT-pre-0.6.txt") for name in sdist_names)
