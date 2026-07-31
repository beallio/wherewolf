import subprocess
import sys
from pathlib import Path


def main():
    """Entry point for the 'wherewolf' command."""
    # Find the app.py relative to this file
    app_path = Path(__file__).parent / "app.py"

    if not app_path.exists():
        print(f"Error: Could not find app.py at {app_path}")
        sys.exit(1)

    # Launch streamlit
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=True)
    except KeyboardInterrupt:
        sys.exit(0)
    # CLI launch boundary: any process startup error should print and fail fast for callers.
    except Exception as e:  # noqa: BLE001
        print(f"Error launching Wherewolf: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
