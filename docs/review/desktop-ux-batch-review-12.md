# Review — desktop-ux-batch (round 12)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `0bf3d35 test(history): harden deletion regression coverage`

## Verdict

**Task 10 accepted — proceed to Task 11.**

Both required tests were added and the implementation was correctly left
untouched, as instructed.

## Gate status

Re-run by the reviewer, not taken on report:

```text
pytest:      519 passed, 7 deselected in 13.80s   (512 before Task 10 — seven new tests)
git status:  clean (empty --porcelain)
```

### Independent verification — the same three mutations from round 11

```text
A: remove the `if not ids_to_delete: return 0` early return    -> 7 passed  (unchanged)
B: write unconditionally (drop `if removed_count:`)            -> FAILED    (was: 5 passed)
C: read raw JSON instead of get_all()                          -> FAILED    (was: 5 passed)
```

B now fails on `test_delete_records_does_not_write_when_no_matching_ids` and C on
`test_delete_records_migrates_v1_entries_left_on_disk`. Both gaps identified in
round 11 are closed. All mutations reverted.

## On mutation A — accepted as unreachable, not as a gap

A still passes, and that is correct rather than a remaining hole. With
`if removed_count:` in place, an empty id set yields zero removals and therefore
no write, so the early return changes no observable behaviour — it is a
short-circuit, not a guard. The plan's requirement ("an empty iterable must not
rewrite the file") is now enforced by the `removed_count` check, which mutation B
proves is covered.

Keep the early return. Do not add a test that reaches inside the function to
assert it exists; that would test the implementation's shape rather than its
behaviour.

## Required changes

None for Task 10.

## Next

Begin **Task 11 — Serialise history records to SQL text**. This is a pure
function in a new `src/wherewolf/services/history_sql_export.py`: no Qt, no
filesystem, no dialogs, exported through `services/__init__.py`. The plan is
specific about the output shape the user chose — newest-first, each record
preceded by a `-- <timestamp>` line, records separated by a blank line, text
ending in exactly one trailing newline — and asks for the **exact full string**
to be asserted for the two-record case, not a substring or a line count. Cover
the empty sequence (returns `""`), a query with trailing whitespace, a query
already ending in a newline (no double blank line), and a query containing an
embedded `--` comment.

STATUS: CHANGES_REQUESTED
