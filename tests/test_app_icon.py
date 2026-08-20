from PyQt6.QtGui import QIcon

from wherewolf.desktop import app_icon


def test_icon_source_yields_an_existing_png() -> None:
    with app_icon.icon_source() as path:
        assert path.exists()
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_load_app_icon_returns_a_usable_icon(qapp) -> None:
    icon = app_icon.load_app_icon()

    assert isinstance(icon, QIcon)
    assert not icon.isNull()
    assert icon.availableSizes()
