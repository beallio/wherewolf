from pathlib import Path

import pytest

from wherewolf.services.export_destination import (
    ExportFormat,
    export_file_filter,
    normalise_destination,
    write_atomically,
)


def test_destination_normalisation_and_filter_are_format_driven() -> None:
    assert normalise_destination(Path("out"), ExportFormat.CSV) == Path("out.csv")
    assert normalise_destination(Path("out.parquet"), ExportFormat.CSV) == Path("out.csv")
    assert normalise_destination(Path("out.CSV"), ExportFormat.CSV) == Path("out.CSV")
    for export_format in ExportFormat:
        selected_filter = export_file_filter(export_format)
        assert f"*.{export_format.value}" in selected_filter
        assert all(
            export_format is other or f"*.{other.value}" not in selected_filter
            for other in ExportFormat
        )


def test_atomic_writer_preserves_existing_bytes_and_removes_temp(tmp_path: Path) -> None:
    target = tmp_path / "out.csv"
    target.write_bytes(b"original")
    with pytest.raises(RuntimeError):
        write_atomically(
            target,
            lambda path: (path.write_bytes(b"partial"), (_ for _ in ()).throw(RuntimeError())),
        )
    assert target.read_bytes() == b"original"
    assert list(tmp_path.glob(".out.csv.*")) == []


def test_atomic_writer_creates_and_replaces(tmp_path: Path) -> None:
    target = tmp_path / "out.csv"

    def write(path: Path) -> None:
        path.write_bytes(b"new")

    write_atomically(target, write)
    assert target.read_bytes() == b"new"
