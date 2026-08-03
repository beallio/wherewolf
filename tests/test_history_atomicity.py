import json
from unittest.mock import patch

import pytest

from wherewolf.storage.history import HistoryManager


def test_history_atomic_write_failure(tmp_path):
    storage_path = tmp_path / "history.json"
    initial_data = [{"query": "SELECT 1", "engine": "DuckDB"}]
    with open(storage_path, "w") as f:
        json.dump(initial_data, f)

    hm = HistoryManager(storage_path=storage_path)

    # Mock json.dump to fail. add_entry removes its temp file and re-raises, so
    # the original OSError reaches the caller unwrapped.
    with (
        patch("json.dump", side_effect=OSError("Disk full")),
        pytest.raises(OSError, match="Disk full"),
    ):
        hm.add_entry("Spark", "SELECT 2", "/path/to/data")

    # Verify the initial data is still there and NOT corrupted/empty
    assert storage_path.exists()
    with open(storage_path, "r") as f:
        data = json.load(f)
        assert data == initial_data
