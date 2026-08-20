# Application icon and desktop entry

## Problem Definition

Wherewolf never sets an icon. `src/wherewolf/desktop/application.py` constructs a
`QApplication` and shows `MainWindow` without touching `QIcon`, and the repository
contains no `.desktop` file, so every surface that displays the app — window title bar,
X11 taskbar, GNOME top bar and dash — falls back to Qt's default placeholder.

Two independent mechanisms are needed, because they are resolved by different code:

1. **Window icon.** `QGuiApplication.setWindowIcon` supplies the icon Qt attaches to each
   window. This is what X11 window managers and the title bar read.
2. **Desktop entry.** Wayland compositors ignore the window icon entirely. GNOME Shell
   matches the surface's xdg-shell `app_id` against an installed desktop entry and takes
   the icon from that entry's `Icon=` key, resolved through the XDG icon theme. Qt derives
   the `app_id` from `QGuiApplication.setDesktopFileName`.

Wherewolf installs with `uv tool install`, not a distro package, so nothing ever places a
desktop entry or themed icon into the user's XDG data directories. That step has to be an
explicit command the user runs.

## Architecture Overview

- `wherewolf.desktop.app_icon` owns locating the packaged PNG and turning it into a
  `QIcon`. It is the single place that knows the resource path and the desktop file name.
- `wherewolf.services.desktop_entry` owns the XDG install: rendering the entry text,
  computing target paths under `$XDG_DATA_HOME`, scaling the 1024x1024 master PNG into the
  standard hicolor sizes, and removing all of it again.
- `wherewolf.desktop.application.main` sets the window icon and the desktop file name
  before `MainWindow` is constructed, so the first window already carries the icon.
- `wherewolf.cli` grows two commands, `install-desktop-entry` and `remove-desktop-entry`,
  which import the service lazily so `--version` still costs no Qt import.

PyQt6 is imported lazily inside the scaling function. The rest of
`wherewolf.services` is Qt-free apart from `settings_service`, and the install path must
stay usable from a CLI that has not created a `QApplication`. `QImage` load, scale, and
save all work without a `QGuiApplication` instance, which was verified before writing this
plan.

## Core Data Structures

```
ICON_RESOURCE: tuple[str, ...]     # package-relative path of the master PNG
DESKTOP_FILE_NAME: str = "wherewolf"   # basename that app_id must match
ICON_NAME: str = "wherewolf"       # value of the entry's Icon= key
ICON_SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256, 512)

@dataclass(frozen=True)
class InstallResult:
    desktop_entry: Path
    icons: tuple[Path, ...]
    icon_cache_refreshed: bool
```

## Public Interfaces

```
wherewolf.desktop.app_icon:
    icon_source() -> AbstractContextManager[Path]
    load_app_icon() -> QIcon

wherewolf.services.desktop_entry:
    data_home() -> Path
    desktop_entry_path(data_home: Path) -> Path
    icon_install_path(data_home: Path, size: int) -> Path
    render_desktop_entry(exec_command: str) -> str
    install_desktop_entry(data_home: Path | None = None, exec_command: str | None = None) -> InstallResult
    remove_desktop_entry(data_home: Path | None = None) -> tuple[Path, ...]

wherewolf.cli:
    main(argv) -> int   # accepts optional "install-desktop-entry" / "remove-desktop-entry"
```

## Dependency Requirements

None added. PyQt6 already ships `QImage`, and the master PNG at
`src/wherewolf/assets/img/wherewolf_logo.png` is already included in the wheel by the
existing `[tool.hatch.build.targets.wheel] packages = ["src/wherewolf"]`.

## Testing Strategy

- `icon_source` yields an existing PNG whose first bytes are the PNG signature, so a broken
  packaging change fails a test rather than shipping a blank icon.
- `load_app_icon` returns a non-null `QIcon` with at least one available size.
- `application.main` calls `setWindowIcon` and `setDesktopFileName` before constructing
  `MainWindow`; asserted by extending the existing ordered-event fake in
  `tests/test_application.py`.
- `render_desktop_entry` emits a `[Desktop Entry]` group with `Type`, `Name`, `Exec`,
  `Icon=wherewolf`, `Terminal=false`, and a `StartupWMClass` matching the desktop file name.
- `install_desktop_entry` into a tmp_path data home writes the entry and one PNG per size,
  each PNG decoding at exactly that size; a second install overwrites rather than failing.
- `remove_desktop_entry` deletes everything install wrote and is a no-op when nothing is
  installed.
- CLI dispatch: each command calls its service function and returns 0; bare `wherewolf`
  still launches the desktop app.
