"""Destination and atomic-write helpers for desktop exports."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path


class ExportFormat(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    PARQUET = "parquet"


def normalise_destination(path: Path, export_format: ExportFormat) -> Path:
    """Return a destination with the selected format extension.

    A mismatched suffix is replaced (rather than silently changing the selected
    format), so the format selected in the UI is always the on-disk format.
    """
    suffix = f".{export_format.value}"
    if path.suffix.lower() == suffix:
        return path
    return path.with_suffix(suffix)


def export_file_filter() -> str:
    return "Export files (" + " ".join(f"*.{fmt.value}" for fmt in ExportFormat) + ")"


def write_atomically(destination: Path, writer: Callable[[Path], None]) -> None:
    """Write via a sibling temporary path and replace only after success."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    os.close(fd)
    temp_path = Path(raw_temp)
    try:
        writer(temp_path)
        os.replace(temp_path, destination)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
