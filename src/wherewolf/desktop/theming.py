"""Application-wide desktop colour themes."""

from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QStyleFactory


class ThemeMode(str, Enum):
    LIGHT = "Light"
    DARK = "Dark"
    FOLLOW_SYSTEM = "Follow system"


PROGRAM_THEME_NAMES = tuple(mode.value for mode in ThemeMode)


def _coerce_mode(mode: ThemeMode | str) -> ThemeMode:
    if isinstance(mode, ThemeMode):
        return mode
    try:
        return ThemeMode(mode)
    except ValueError:
        return ThemeMode.FOLLOW_SYSTEM


def resolve_theme_mode(
    mode: ThemeMode | str,
    system_scheme: Qt.ColorScheme | None = None,
) -> ThemeMode:
    """Resolve an explicit or system-following mode to Light or Dark."""
    requested = _coerce_mode(mode)
    if requested is not ThemeMode.FOLLOW_SYSTEM:
        return requested

    scheme = system_scheme
    if scheme is None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            try:
                hints = app.styleHints()
                if hints is not None:
                    scheme = hints.colorScheme()
            except (AttributeError, RuntimeError):
                scheme = None
    return ThemeMode.DARK if scheme is Qt.ColorScheme.Dark else ThemeMode.LIGHT


def build_palette(mode: ThemeMode | str) -> QPalette:
    """Build a Fusion-compatible palette with distinguishable alternating rows."""
    resolved = resolve_theme_mode(mode)
    if resolved is ThemeMode.DARK:
        colours = {
            QPalette.ColorRole.Window: "#2b2b2b",
            QPalette.ColorRole.Base: "#1e1e1e",
            QPalette.ColorRole.AlternateBase: "#2a2a2a",
            QPalette.ColorRole.Text: "#f0f0f0",
            QPalette.ColorRole.Button: "#3c3f41",
            QPalette.ColorRole.ButtonText: "#f0f0f0",
            QPalette.ColorRole.Highlight: "#3465a4",
            QPalette.ColorRole.HighlightedText: "#ffffff",
            QPalette.ColorRole.Link: "#8ab4f8",
        }
    else:
        colours = {
            QPalette.ColorRole.Window: "#f0f0f0",
            QPalette.ColorRole.Base: "#ffffff",
            QPalette.ColorRole.AlternateBase: "#f7f7f7",
            QPalette.ColorRole.Text: "#202020",
            QPalette.ColorRole.Button: "#e6e6e6",
            QPalette.ColorRole.ButtonText: "#202020",
            QPalette.ColorRole.Highlight: "#3874c8",
            QPalette.ColorRole.HighlightedText: "#ffffff",
            QPalette.ColorRole.Link: "#0645ad",
        }

    palette = QPalette()
    for role, colour in colours.items():
        palette.setColor(role, QColor(colour))
    return palette


def message_severity_color(severity: str, palette: QPalette) -> QColor:
    """Return a legible severity colour for the supplied widget palette."""
    is_dark = palette.color(QPalette.ColorRole.Base).lightness() < 128
    colours = (
        {
            "error": "#ffb4ab",
            "warning": "#ffb95d",
            "info": "#a8c7fa",
        }
        if is_dark
        else {
            "error": "#b3261e",
            "warning": "#7a4e00",
            "info": "#005ac1",
        }
    )
    return QColor(colours.get(severity, palette.color(QPalette.ColorRole.Text)))


def apply_program_theme(app: QApplication, mode: ThemeMode | str) -> ThemeMode:
    """Apply a program theme and return the resolved Light/Dark mode."""
    resolved = resolve_theme_mode(mode)
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)
    app.setPalette(build_palette(resolved))
    return resolved


__all__ = [
    "PROGRAM_THEME_NAMES",
    "ThemeMode",
    "apply_program_theme",
    "build_palette",
    "message_severity_color",
    "resolve_theme_mode",
]
