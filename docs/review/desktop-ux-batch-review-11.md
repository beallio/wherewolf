# Review — desktop-ux-batch (round 11)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `ac8b7c6 feat(history): delete history records by id`

## Verdict

**Task 10 is NOT accepted.** The implementation is correct. The tests do not
defend it — three separate mutations of `delete_records` leave all five new tests
green, including the one the plan added specifically to protect the v1 migration.

Do not advance to Task 11. Strengthen the tests in place, re-run the gates,
re-commit, and re-mark the round. **Do not change the implementation** — it is
right as written.

## What was measured

```text
A: remove the `if not ids_to_delete: return 0` early return    -> 5 passed
B: write unconditionally (drop `if removed_count:`)            -> 5 passed
C: read raw JSON instead of get_all() (skips the v1 migration) -> 5 passed
```

All three reverted.

### Why A and B pass

They mask each other. `delete_records([])` returns at the early guard before ever
reaching the write, so the "no ids ⇒ no write" test passes with **either** guard
present. Neither guard is independently covered.

### Why C passes — this is the one that matters

`test_delete_records_preserves_a_migrated_legacy_record` calls `manager.get_all()`
twice before the delete (to capture `migrated_legacy`, then `removable`). The
first of those calls already migrated the file and rewrote it as v2. By the time
`delete_records` runs there is no v1 entry left on disk, so the test cannot
distinguish a `get_all()`-based implementation from one that parses the raw JSON.

The plan called for that case precisely because *"a delete implemented against the
raw JSON would corrupt it"*. As written, the test does not prove that.

## Required changes

### MECHANICAL — add a test that deletes while a v1 entry is still raw on disk

The trick is to seed a **mixed** file: one v2 entry whose id you already know, and
one legacy v1 entry. Then call `delete_records` **without** calling `get_all()`
first, and assert against the file on disk.

```python
def test_delete_records_migrates_v1_entries_left_on_disk(tmp_path: Path) -> None:
    history_file = tmp_path / "history.json"
    v2_entry = {
        "schema_version": 2,
        "id": "f46d098f-4cdc-4ad7-bd40-4c6db2ad0b64",
        "timestamp": "2026-08-02T12:00:00+00:00",
        "engine": "duckdb",
        "query": "SELECT removable",
        "path": "",
        "catalog": {},
    }
    v1_entry = {
        "timestamp": "2026-08-01T12:00:00+00:00",
        "engine": "duckdb",
        "query": "SELECT legacy",
        "path": "",
    }
    history_file.write_text(json.dumps([v2_entry, v1_entry]))

    # delete WITHOUT calling get_all() first, so the v1 entry is still raw on disk
    manager = HistoryManager(storage_path=history_file)
    assert manager.delete_records([v2_entry["id"]]) == 1

    on_disk = json.loads(history_file.read_text())
    assert len(on_disk) == 1
    assert on_disk[0]["query"] == "SELECT legacy"
    assert on_disk[0]["schema_version"] == 2
    assert "id" in on_disk[0]
```

Adapt it to this file's `storage_dir` fixture rather than `tmp_path` if that is
cleaner. This test was written and run by the reviewer against both
implementations before being prescribed:

```text
against the current implementation      -> 1 passed
against the raw-JSON implementation (C) -> 1 failed
```

### MECHANICAL — cover the `if removed_count:` write guard independently

The existing empty-iterable test cannot reach it. Add a case that patches
`_write_history` and deletes an id that does not exist, asserting it was **not**
called:

```python
with patch.object(manager, "_write_history") as write_history:
    assert manager.delete_records(["f46d098f-4cdc-4ad7-bd40-4c6db2ad0b64"]) == 0
write_history.assert_not_called()
```

The current unknown-id test compares file text, which is insensitive to a
rewrite that produces byte-identical output.

Keep all five existing tests — they are correct, just not sufficient.

## Not at issue

- `delete_records` builds survivors from `get_all()`, writes through
  `_write_history`, returns the removed count, ignores unknown ids, and does not
  rewrite for an empty iterable. Every behavioural requirement in the plan is
  met.
- `set(entry_ids)` correctly handles a generator argument (consumed once).
- The redundancy between the two guards is harmless. **Keep both** — after the
  changes above, each is covered by its own test.

## Gate status

```text
tree: clean before and after review (all mutations reverted)
```

The full suite was not re-run this round; the coverage gap above blocks
acceptance regardless of the tally.

STATUS: CHANGES_REQUESTED
