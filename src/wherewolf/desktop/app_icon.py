"""The packaged application icon and the desktop-entry name Qt reports to the compositor."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path

from PyQt6.QtGui import QIcon, QPixmap

#: Basename of the installed desktop entry. Wayland compositors match the surface's
#: ``app_id`` against this name to find the icon, so it must equal the ``.desktop``
#: file's stem exactly.
DESKTOP_FILE_NAME = "wherewolf"

ICON_RESOURCE = ("assets", "img", "wherewolf_logo.png")


@contextmanager
def icon_source() -> Iterator[Path]:
    """Yield a real filesystem path to the packaged master icon.

    ``as_file`` extracts the resource when the distribution is zipped, and the extracted
    copy is deleted on exit, so callers must read the file inside the block.
    """
    resource = files("wherewolf")
    for part in ICON_RESOURCE:
        resource = resource / part
    with as_file(resource) as path:
        yield path


def load_app_icon() -> QIcon:
    """Load the application icon into memory, detached from the file it came from."""
    with icon_source() as path:
        pixmap = QPixmap(str(path))
    return QIcon(pixmap)
