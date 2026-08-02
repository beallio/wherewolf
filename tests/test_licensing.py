import tomllib
from pathlib import Path


def test_license_file_is_gpl3() -> None:
    license_text = Path("LICENSE").read_text(encoding="utf-8")

    assert "GNU GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3" in license_text


def test_mit_pre_06_license_file_exists() -> None:
    mit_license = Path("LICENSES/MIT-pre-0.6.txt").read_text(encoding="utf-8")

    assert "MIT License" in mit_license
    assert "Copyright (c) 2026 David Beall" in mit_license


def test_pyproject_has_gpl3_license_and_files() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["license"] == "GPL-3.0-only"
    assert "license-files" in project
    assert "LICENSE" in project["license-files"]
    assert "LICENSES/*" in project["license-files"]


def test_notice_text_mentions_gpl_and_mit_history() -> None:
    notice = Path("NOTICE.md").read_text(encoding="utf-8")

    assert "GPL-3.0-only" in notice
    assert "up to and including 0.5.2" in notice
    assert "MIT" in notice


def test_readme_mentions_gpl_and_not_old_mit_badge() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "GPL-3.0-only" in readme
    assert "License: MIT" not in readme
