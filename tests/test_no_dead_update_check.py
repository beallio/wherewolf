"""The update-check preference must not exist while nothing implements it.

A "Check for updates on startup" checkbox shipped with no client behind it: no HTTP
call anywhere in the package, only a persisted boolean. Ticking it did nothing, which
is worse than not offering the option — it is a promise the app cannot keep.

If an update client is ever written, delete this module along with adding it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QCheckBox

from wherewolf.desktop.main_window import MainWindow, PreferencesDialog
from wherewolf.services.settings_service import SettingsService

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "wherewolf"


@pytest.fixture
def window(qtbot) -> MainWindow:
    win = MainWindow()
    qtbot.addWidget(win)
    return win


def test_no_update_check_control_is_offered(window: MainWindow, qtbot) -> None:
    """No widget may advertise update checking.

    The dialog must be constructed explicitly: it is built on demand, so searching
    MainWindow's children would pass whether or not the checkbox exists.
    """
    dialog = PreferencesDialog(window._settings_service, window._file_dialog_service, window)
    qtbot.addWidget(dialog)

    boxes = [box.text() for box in dialog.findChildren(QCheckBox)]
    offending = [text for text in boxes if "update" in text.lower()]
    assert boxes, "fixture failed: the Preferences dialog exposes no checkboxes at all"
    assert not offending, (
        f"a control offering update checks is present, but nothing implements it: {offending}"
    )
    assert not hasattr(dialog, "update_check_enabled")


def test_settings_service_exposes_no_update_check_api() -> None:
    """The orphaned persistence API must go with the control.

    Leaving it recreates the pattern that produced this repo's dead widgets: working,
    tested code that no user can reach.
    """
    leftovers = [name for name in dir(SettingsService) if "update_check" in name.lower()]
    assert not leftovers, f"orphaned update-check settings API: {leftovers}"


def test_no_update_check_client_exists_in_the_package() -> None:
    """Guard the premise: if someone adds a client, this test should be deleted, not muted."""
    markers = ("update_check", "check_for_update", "releases/latest")
    hits: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker in text:
                hits.append(f"{path.relative_to(SRC_ROOT)}: {marker}")

    assert not hits, (
        "update-check references remain in the package; either implement the client and "
        f"delete this test module, or remove the references: {hits}"
    )
