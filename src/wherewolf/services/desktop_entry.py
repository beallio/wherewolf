"""Install the XDG desktop entry and themed icons Wayland needs to show the app icon.

Wherewolf is installed with ``uv tool install`` rather than a distribution package, so
nothing ever places a desktop entry in the user's data directories. Without one, GNOME
Shell has no icon to resolve for the window's ``app_id`` and falls back to a placeholder,
however the application sets ``QGuiApplication.setWindowIcon``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from wherewolf.desktop.app_icon import DESKTOP_FILE_NAME, icon_source

ICON_NAME = DESKTOP_FILE_NAME
EXEC_NAME = "wherewolf-desktop"

#: The sizes the hicolor theme defines for application icons. GNOME picks the nearest
#: match, so shipping only the master would leave it downscaling 1024px for a 22px panel.
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


@dataclass(frozen=True)
class InstallResult:
    """Paths written by :func:`install_desktop_entry`."""

    desktop_entry: Path
    icons: tuple[Path, ...]
    icon_cache_refreshed: bool


def _xdg_data_home() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    if configured:
        return Path(configured)
    return Path.home() / ".local" / "share"


def data_home() -> Path:
    """Return ``$XDG_DATA_HOME``, falling back to the specified default."""
    return _xdg_data_home()


def desktop_entry_path(data_home: Path) -> Path:
    return data_home / "applications" / f"{DESKTOP_FILE_NAME}.desktop"


def icon_install_path(data_home: Path, size: int) -> Path:
    return data_home / "icons" / "hicolor" / f"{size}x{size}" / "apps" / f"{ICON_NAME}.png"


def render_desktop_entry(exec_command: str) -> str:
    """Render the desktop entry.

    ``StartupWMClass`` covers X11, where the window class rather than the ``app_id``
    is what associates a window with this entry.
    """
    lines = (
        "[Desktop Entry]",
        "Type=Application",
        "Name=Wherewolf",
        "GenericName=SQL Workbench",
        "Comment=A local SQL workbench for CSV, Parquet, JSON, and XLSX files",
        f"Exec={exec_command}",
        f"Icon={ICON_NAME}",
        "Terminal=false",
        "Categories=Development;Database;",
        f"StartupWMClass={DESKTOP_FILE_NAME}",
    )
    return "\n".join(lines) + "\n"


def _write_scaled_icons(target_home: Path) -> tuple[Path, ...]:
    # Imported here so the module stays usable from a CLI that never starts Qt; QImage
    # itself needs no QGuiApplication for load, scale, and save.
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage

    with icon_source() as source:
        master = QImage(str(source))
    if master.isNull():
        raise RuntimeError("the packaged application icon could not be read")

    written: list[Path] = []
    for size in ICON_SIZES:
        scaled = master.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        path = icon_install_path(target_home, size)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not scaled.save(str(path), "PNG"):
            raise RuntimeError(f"could not write {path}")
        written.append(path)
    return tuple(written)


def _refresh_icon_cache(target_home: Path) -> bool:
    """Best effort: a stale GTK icon cache hides freshly installed icons."""
    tool = shutil.which("gtk-update-icon-cache")
    theme_dir = target_home / "icons" / "hicolor"
    if tool is None or not (theme_dir / "index.theme").exists():
        return False
    result = subprocess.run(
        [tool, "--force", "--quiet", str(theme_dir)],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def install_desktop_entry(
    data_home: Path | None = None, exec_command: str | None = None
) -> InstallResult:
    """Write the desktop entry and themed icons into the user's data directory."""
    target_home = data_home if data_home is not None else _xdg_data_home()
    if exec_command is None:
        exec_command = shutil.which(EXEC_NAME) or EXEC_NAME

    icons = _write_scaled_icons(target_home)
    entry_path = desktop_entry_path(target_home)
    entry_path.parent.mkdir(parents=True, exist_ok=True)
    entry_path.write_text(render_desktop_entry(exec_command), encoding="utf-8")

    return InstallResult(
        desktop_entry=entry_path,
        icons=icons,
        icon_cache_refreshed=_refresh_icon_cache(target_home),
    )


def remove_desktop_entry(data_home: Path | None = None) -> tuple[Path, ...]:
    """Delete everything :func:`install_desktop_entry` wrote, reporting what was removed."""
    target_home = data_home if data_home is not None else _xdg_data_home()
    candidates = [desktop_entry_path(target_home)]
    candidates.extend(icon_install_path(target_home, size) for size in ICON_SIZES)

    removed: list[Path] = []
    for path in candidates:
        if path.exists():
            path.unlink()
            removed.append(path)
    return tuple(removed)
