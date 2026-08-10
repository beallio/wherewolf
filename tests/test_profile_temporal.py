from pathlib import Path
from uuid import uuid4

import duckdb

from wherewolf.domain import CatalogEntry, SourceFormat
from wherewolf.execution.registry import _DuckDBAdapter


def test_duckdb_profile_preserves_temporal_summarize_statistics(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    with duckdb.connect(database=":memory:") as connection:
        connection.execute(
            f"""
            COPY (
                SELECT
                    strftime(TIMESTAMP '2024-01-01' + INTERVAL (i) SECOND,
                             '%Y-%m-%d %H:%M:%S') AS event_ts,
                    i AS amount
                FROM range(100) t(i)
            ) TO '{csv_path}' (HEADER, DELIMITER ',')
            """
        )

    entry = CatalogEntry(
        id=uuid4(),
        alias="events",
        path=csv_path,
        source_format=SourceFormat.CSV,
    )
    result = _DuckDBAdapter(uuid4()).profile_dataset(entry)

    assert result.error_type is None, result.error_message
    assert result.error_message is None
    assert result.profiles is not None
    assert len(result.profiles) == 2

    temporal_profile = next(profile for profile in result.profiles if profile.name == "event_ts")
    assert temporal_profile.data_type == "TIMESTAMP", (
        "Temporal fixture was not inferred as TIMESTAMP; it cannot exercise temporal profiling."
    )
    assert temporal_profile.avg is not None and temporal_profile.avg.startswith("2024-01-01")
    assert temporal_profile.q25 is not None and temporal_profile.q25.startswith("2024-01-01")
    assert temporal_profile.q50 is not None and temporal_profile.q50.startswith("2024-01-01")
    assert temporal_profile.q75 is not None and temporal_profile.q75.startswith("2024-01-01")

    amount_profile = next(profile for profile in result.profiles if profile.name == "amount")
    assert amount_profile.avg == "49.5"
