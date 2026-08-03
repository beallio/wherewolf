"""Console entry point for the native desktop application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the native Qt application for the ``wherewolf`` console script.

    ``--version`` is answered before Qt is touched, so it works over SSH and on a box
    with no display — which is where you most need to ask which build is installed.
    """
    parser = argparse.ArgumentParser(
        prog="wherewolf",
        description="Wherewolf — a local SQL workbench.",
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

    # Imported here, not at module scope: --version must not pay for Qt.
    from wherewolf.desktop.application import main as desktop_main

    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
