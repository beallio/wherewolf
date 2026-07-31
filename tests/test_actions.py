from PyQt6.QtGui import QKeySequence

from wherewolf.desktop import DesktopActions, build_actions


def test_build_actions_contains_expected_shortcuts_and_states(qtbot) -> None:
    actions = build_actions()

    assert isinstance(actions, DesktopActions)
    assert actions.run.text() == "Run"
    assert actions.run.isEnabled()
    assert actions.run.shortcut() == QKeySequence("Ctrl+Return")

    assert actions.cancel.text() == "Cancel"
    assert not actions.cancel.isEnabled()
    assert actions.cancel.shortcut() == QKeySequence("Ctrl+.")

    assert not actions.format_sql.isEnabled()
    assert "Phase 3" in actions.format_sql.toolTip()

    assert not actions.add_datasets.isEnabled()
    assert "Phase 3" in actions.add_datasets.toolTip()
