# Review — desktop-ux-batch (round 13)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `db298d4 feat(history): serialise history records to SQL text`

## Verdict

**Task 11 is NOT accepted.** The module shape, the output format, and six of the
seven tests are right. The added timestamp sort compares ISO strings, which
orders records **wrongly whenever two timestamps carry different UTC offsets** —
so the file advertises newest-first and delivers the opposite.

Do not advance to Task 12. Fix in place, re-run the gates, re-commit, re-mark.

## The defect

The plan said "takes an ordered sequence … newest-first", which is ambiguous
about whether the function sorts or preserves caller order. Sorting is the
defensible reading and it is the safer one — Task 13 will hand this function an
arbitrary user selection — so **keep the sort**. The comparison is the problem:

```python
key=lambda record: str(record.get("timestamp", "")),
```

`history.py:94` stores `datetime.now().astimezone().isoformat()`, so the offset
reflects wherever the machine was when the query ran. Any user who travels, or
who crosses a DST boundary, accumulates history with mixed offsets. Measured
against the real function:

```text
chronological order : ['2026-08-11T09:30:00-07:00', '2026-08-11T10:00:00+00:00']
plain string order  : ['2026-08-11T10:00:00+00:00', '2026-08-11T09:30:00-07:00']

--- exported file ---
-- 2026-08-11T10:00:00+00:00
SELECT older_instant

-- 2026-08-11T09:30:00-07:00
SELECT newer_instant
```

`09:30-07:00` is 16:30 UTC — six and a half hours **after** `10:00+00:00` — yet it
is written last.

This codebase already knows string comparison is wrong here: `HistoryItem`
(`history_dock.py:16-34`) parses timestamps into `datetime` objects precisely so
the History dock sorts chronologically. The export must match the dock.

## Required changes

### MECHANICAL — sort by the parsed instant

Add the import and the key function, and use it:

```python
from datetime import UTC, datetime
```

```python
    ordered_records = sorted(valid_records, key=_recorded_instant, reverse=True)
```

```python
def _recorded_instant(record: Mapping[str, object]) -> tuple[int, datetime]:
    """Order records by their real instant, tolerating unparseable timestamps."""
    try:
        parsed = datetime.fromisoformat(str(record.get("timestamp", "")))
    except ValueError:
        return (0, datetime.min.replace(tzinfo=UTC))
    return (1, parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC))
```

The `tzinfo` normalisation is load-bearing: comparing a naive `datetime` with an
aware one raises `TypeError`, and `_migrate_v1_entry` can leave naive timestamps
in migrated records. The leading `0`/`1` rank keeps unparseable timestamps from
crashing the sort and pushes them to the end of the file. `sorted` is stable, so
records sharing an instant keep their caller order.

This patch was applied and measured by the reviewer before being prescribed:

```text
mixed offsets   first='SELECT newer'
naive + aware   first='SELECT aware_newer'
unparseable     first='SELECT valid'
tests/test_history_sql_export.py: 7 passed
```

All seven of your existing tests still pass with it. The reviewer's tree was
reverted; the patch is yours to apply.

### MECHANICAL — add the regression tests

Three cases, each of which must fail against the current string sort (record the
red output for the first one at minimum):

1. **mixed offsets** — `2026-08-11T09:30:00-07:00` (newer instant) and
   `2026-08-11T10:00:00+00:00` (older); assert the `-07:00` record is written
   first;
2. **naive and aware mixed** — assert no `TypeError` and that the later instant
   wins;
3. **unparseable timestamp** — assert the valid record is written first and the
   junk record still appears rather than being dropped.

## Not at issue

- Module location, `services/__init__.py` export, and the no-Qt/no-filesystem
  constraint are all correct.
- The output format is exactly as specified: `-- <timestamp>` header, blank line
  between records, one trailing newline, trailing query whitespace preserved,
  embedded `--` comments untouched, no double blank line for a query that already
  ends in a newline.
- Skipping records whose `query` is absent or non-string is correct.

## Non-blocking observation

`assert isinstance(query, str)` inside the loop is a type-narrowing assert in
production code; it is stripped under `python -O`. It cannot fire — the
comprehension above already filtered on exactly that predicate. Prefer binding
the narrowed value in the filter, or a `cast`. Do not spend a round on it.

STATUS: CHANGES_REQUESTED
