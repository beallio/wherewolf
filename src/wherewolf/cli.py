"""Console entry point for Wherewolf's desktop and headless workflows."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from wherewolf.services.export_destination import ExportFormat
from wherewolf.services.headless_query import (
    HeadlessQueryError,
    HeadlessQueryOptions,
    HeadlessQueryRunner,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wherewolf",
        description="Wherewolf — a local SQL workbench.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="print the version and build commit, then exit",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser(
        "install-desktop-entry",
        help="install the XDG desktop entry and themed application icons",
    )
    commands.add_parser(
        "remove-desktop-entry",
        help="remove the installed XDG desktop entry and application icons",
    )
    query = commands.add_parser(
        "query",
        help="run one DuckDB SQL query and export every result row to a file",
    )
    query.add_argument("sql", help="one SQL statement to execute")
    query.add_argument(
        "--dataset",
        action="append",
        default=[],
        metavar="ALIAS=PATH",
        help="bind a local dataset file to a SQL alias; repeat for multiple datasets",
    )
    query.add_argument(
        "--format",
        type=ExportFormat,
        choices=tuple(ExportFormat),
        default=ExportFormat.CSV,
        help="output format (default: csv)",
    )
    query.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="exact destination path for the export",
    )
    query.add_argument(
        "--force",
        action="store_true",
        help="allow replacement of an existing output file",
    )
    return parser


def _run_query(options: HeadlessQueryOptions) -> int:
    try:
        destination = HeadlessQueryRunner().run(options)
    except HeadlessQueryError as exc:
        print(f"wherewolf query: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {destination}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch desktop management, headless exports, or the native Qt application."""
    args = _build_parser().parse_args(argv)

    if args.version:
        from wherewolf import build_identifier

        print(build_identifier())
        return 0

    if args.command == "query":
        return _run_query(
            HeadlessQueryOptions(
                sql=args.sql,
                datasets=tuple(args.dataset),
                export_format=args.format,
                output=args.output,
                force=args.force,
            )
        )

    # Imported lazily because managing a desktop entry remains a headless operation.
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

    # No subcommand preserves the desktop application's original entry point.
    from wherewolf.desktop.application import main as desktop_main

    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
