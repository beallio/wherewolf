"""Render saved query-history records as one portable SQL document."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime


def _recorded_instant(record: Mapping[str, object]) -> tuple[int, datetime]:
    """Order records by their real instant, tolerating unparseable timestamps."""
    try:
        parsed = datetime.fromisoformat(str(record.get("timestamp", "")))
    except ValueError:
        return (0, datetime.min.replace(tzinfo=UTC))
    return (1, parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC))


def serialise_history_records_to_sql(records: Sequence[Mapping[str, object]]) -> str:
    """Return valid history queries as newest-first SQL text.

    Each record retains its stored timestamp as a SQL comment. Queries are not
    otherwise transformed, so embedded comments and trailing spaces survive
    export; only terminal line endings are normalised to keep one blank line
    between records and exactly one final newline.
    """
    valid_records = [record for record in records if isinstance(record.get("query"), str)]
    if not valid_records:
        return ""

    ordered_records = sorted(valid_records, key=_recorded_instant, reverse=True)
    blocks = []
    for record in ordered_records:
        query = record["query"]
        assert isinstance(query, str)
        normalised_query = query.rstrip("\r\n")
        blocks.append(f"-- {record.get('timestamp', '')}\n{normalised_query}")

    return "\n\n".join(blocks) + "\n"


__all__ = ["serialise_history_records_to_sql"]
