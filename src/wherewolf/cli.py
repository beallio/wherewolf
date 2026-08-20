"""Console entry point for the native desktop application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the native Qt application for the ``wherewolf`` console script.

    ``--version`` and the desktop-entry commands are answered before Qt is touched, so it works over SSH and on a box
    with no display — which is where you most need to ask which build is installed.
    """
    parser = argparse.ArgumentParser(
        prog="wherewolf",
        description="Wherewolf — a local SQL workbench.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("install-desktop-entry", "remove-desktop-entry"),
        help=(
            "install-desktop-entry writes the XDG desktop entry and themed icons that "
            "Wayland needs to show the application icon; remove-desktop-entry deletes them. "
            "With no command, the desktop application starts."
        ),
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="print the version and build commit, then exit",
    )
    args = parser.parse_args(argv)

    if args.version:
        from wherewolf import build_identifier

        print(build_identifier())
        return 0

    # Imported lazily for the same reason as the desktop entry point below: managing the
    # desktop entry is a headless operation and must not require a display.
    if args.command == "install-desktop-entry":
        from wherewolf.services import desktop_entry

        result = desktop_entry.install_desktop_entry()
        print(f"Installed {result.desktop_entry}")
        print(f"Installed {len(result.icons)} icons under {result.icons[0].parents[3]}")
        return 0

    if args.command == "remove-desktop-entry":
        from wherewolf.services import desktop_entry

        removed = desktop_entry.remove_desktop_entry()
        if not removed:
            print("Nothing to remove.")
            return 0
        for path in removed:
            print(f"Removed {path}")
        return 0

    # Imported here, not at module scope: --version must not pay for Qt.
    from wherewolf.desktop.application import main as desktop_main

    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
