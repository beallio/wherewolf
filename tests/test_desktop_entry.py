from pathlib import Path

from PyQt6.QtGui import QImage

from wherewolf.services import desktop_entry


def _entry_values(text: str) -> dict[str, str]:
    lines = text.splitlines()
    assert lines[0] == "[Desktop Entry]"
    return dict(line.split("=", 1) for line in lines[1:] if line)


def test_render_desktop_entry_declares_the_icon_and_window_class() -> None:
    values = _entry_values(desktop_entry.render_desktop_entry("/usr/bin/wherewolf-desktop"))

    assert values["Type"] == "Application"
    assert values["Name"] == "Wherewolf"
    assert values["Exec"] == "/usr/bin/wherewolf-desktop"
    assert values["Icon"] == desktop_entry.ICON_NAME
    assert values["Terminal"] == "false"
    assert values["StartupWMClass"] == desktop_entry.DESKTOP_FILE_NAME


def test_install_desktop_entry_writes_entry_and_every_icon_size(tmp_path: Path) -> None:
    result = desktop_entry.install_desktop_entry(
        data_home=tmp_path, exec_command="/opt/wherewolf-desktop"
    )

    assert result.desktop_entry == tmp_path / "applications" / "wherewolf.desktop"
    assert result.desktop_entry.read_text().startswith("[Desktop Entry]\n")
    assert "/opt/wherewolf-desktop" in result.desktop_entry.read_text()

    assert len(result.icons) == len(desktop_entry.ICON_SIZES)
    for size, path in zip(desktop_entry.ICON_SIZES, result.icons, strict=True):
        assert path == (
            tmp_path / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "wherewolf.png"
        )
        image = QImage(str(path))
        assert (image.width(), image.height()) == (size, size)


def test_install_desktop_entry_is_idempotent(tmp_path: Path) -> None:
    first = desktop_entry.install_desktop_entry(data_home=tmp_path, exec_command="/opt/w")
    second = desktop_entry.install_desktop_entry(data_home=tmp_path, exec_command="/opt/w")

    assert first.desktop_entry == second.desktop_entry
    assert first.icons == second.icons


def test_install_desktop_entry_defaults_exec_to_the_installed_console_script(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(desktop_entry.shutil, "which", lambda name: f"/somewhere/{name}")

    result = desktop_entry.install_desktop_entry(data_home=tmp_path)

    assert "Exec=/somewhere/wherewolf-desktop" in result.desktop_entry.read_text()


def test_data_home_honours_xdg_data_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert desktop_entry.data_home() == tmp_path / "xdg"

    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert desktop_entry.data_home() == tmp_path / "home" / ".local" / "share"


def test_remove_desktop_entry_deletes_what_install_wrote(tmp_path: Path) -> None:
    installed = desktop_entry.install_desktop_entry(data_home=tmp_path, exec_command="/opt/w")

    removed = desktop_entry.remove_desktop_entry(data_home=tmp_path)

    assert set(removed) == {installed.desktop_entry, *installed.icons}
    assert not installed.desktop_entry.exists()
    assert all(not path.exists() for path in installed.icons)


def test_remove_desktop_entry_is_a_no_op_when_nothing_is_installed(tmp_path: Path) -> None:
    assert desktop_entry.remove_desktop_entry(data_home=tmp_path) == ()
