from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from wherewolf.desktop.theming import (
    ThemeMode,
    apply_program_theme,
    build_palette,
    message_severity_color,
    resolve_theme_mode,
)
from wherewolf.desktop.widgets.result_table_view import ResultTableView


def test_light_and_dark_palettes_define_expected_window_and_base_colours(qtbot) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    light = build_palette(ThemeMode.LIGHT)
    dark = build_palette(ThemeMode.DARK)

    assert light.color(QPalette.ColorRole.Window) == QColor("#f0f0f0")
    assert light.color(QPalette.ColorRole.Base) == QColor("#ffffff")
    assert dark.color(QPalette.ColorRole.Window) == QColor("#2b2b2b")
    assert dark.color(QPalette.ColorRole.Base) == QColor("#1e1e1e")


def test_follow_system_resolves_dark_light_and_unknown_to_safe_modes(qtbot) -> None:
    assert resolve_theme_mode(ThemeMode.FOLLOW_SYSTEM, Qt.ColorScheme.Dark) is ThemeMode.DARK
    assert resolve_theme_mode(ThemeMode.FOLLOW_SYSTEM, Qt.ColorScheme.Light) is ThemeMode.LIGHT
    assert resolve_theme_mode(ThemeMode.FOLLOW_SYSTEM, Qt.ColorScheme.Unknown) is ThemeMode.LIGHT


def test_application_theme_updates_palette_and_keeps_alternate_rows_distinct(qtbot) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
        apply_program_theme(app, mode)
        style = app.style()
        assert style is not None
        assert style.objectName().lower() == "fusion"
        palette = app.palette()
        assert palette.alternateBase().color() != palette.base().color()
        grid = ResultTableView()
        qtbot.addWidget(grid)
        assert grid.palette().alternateBase().color() != grid.palette().base().color()


def test_message_severity_colours_are_distinct_and_readable_in_both_themes(qtbot) -> None:
    for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
        palette = build_palette(mode)
        colours = {
            severity: message_severity_color(severity, palette)
            for severity in ("error", "warning", "info")
        }

        assert colours["error"].red() > colours["error"].green()
        assert colours["error"].red() > colours["error"].blue()
        assert len({colour.name() for colour in colours.values()}) == 3
        assert all(
            _colour_contrast(colour, palette.color(QPalette.ColorRole.Base)) >= 4.5
            for colour in colours.values()
        )


def _colour_contrast(first: QColor, second: QColor) -> float:
    def _luminance(colour: QColor) -> float:
        channels = (colour.redF(), colour.greenF(), colour.blueF())
        linear = tuple(
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        )
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
