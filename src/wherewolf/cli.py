"""Console entry point for the native desktop application."""

from wherewolf.desktop.application import main as desktop_main


def main() -> int:
    """Launch the native Qt application for the ``wherewolf`` console script."""
    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
