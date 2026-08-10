# Review — catalog-elide-temporal-profile (round 03)

Branch: `feat/catalog-elide-temporal-profile`
Reviewed against: `docs/plans/2026-08-10_catalog-elide-temporal-profile.md`
Round contents: `a5a7882` — Task 2, "Stretch the File column to the available width".

## Verdict

**Task 2 is NOT accepted — one test change, then it is done.**

The production change is exactly the amended specification and needs no edit. Both
new tests are well-formed. One of them, however, passes under the mutation it was
supposed to catch.

## Gate status

Re-run independently on `a5a7882`:

```text
./run.sh uv run pytest -q     497 passed, 7 deselected in 12.97s
./run.sh uv run ty check src/ All checks passed!
git status --porcelain        (empty)
```

## Required change

### R3 — `test_catalog_file_column_keeps_paths_distinct_at_user_dock_width` is vacuous

**First, my error, not yours.** Review 02 told you this test "fails under the
`Interactive` variant". I measured that against the user's real paths from
`fix/Screenshot_20260802_132729.png` and then, in the same note, told you to use
the synthetic `/very/long/shared/prefix/directory/segments/` fixture. Those two
instructions are not compatible. You followed them exactly as written.

Orchestrator mutation check — columns 2 and 3 reverted to `Interactive`, then the
test re-run:

```text
1 passed, 15 deselected in 0.61s
```

It should have failed. Measured cause, both variants run through your test's exact
setup sequence:

| fixture | modes on cols 2,3 | sections | File paint budget | rows distinct? |
|---|---|---|---|---|
| `/very/long/…/segments/` | ResizeToContents | `[100, 190, 53, 93]` | 182 px | yes |
| `/very/long/…/segments/` | Interactive | `[100, 136, 100, 100]` | 128 px | **yes** |
| `/run/media/beallio/external/datasets/` | ResizeToContents | `[100, 190, 53, 93]` | 182 px | yes |
| `/run/media/beallio/external/datasets/` | Interactive | `[100, 136, 100, 100]` | 128 px | **no** |

At 128 px the synthetic fixture renders `'/very/long…rs.parquet'` versus
`…ns.parquet` — distinct by a single character, and distinct for a reason that has
nothing to do with the resize modes. The real paths render `'/run/medi…s.parquet'`
for both, because `customers` and `loans` share the `s.parquet` tail at that
budget.

**Required:** change that test's two fixture paths to the user's real ones:

```python
first_path = Path("/run/media/beallio/external/datasets/customers.parquet")
second_path = Path("/run/media/beallio/external/datasets/loans.parquet")
```

Change nothing else in it — the 450 px dock size, the `available_width` arithmetic,
and the failure message are all correct. Leave
`test_catalog_file_column_elides_paths_in_the_middle` on its current synthetic
fixture; at its pinned 258 px width that test is already proven live.

After the change, verify the test is live before you mark the round: set columns 2
and 3 to `Interactive`, run the test, confirm it fails and that the message prints
the two identical strings and `available_width=128`, then revert the mutation and
confirm `git status --porcelain` is empty. Record the failure output in the session
log.

## Accepted without change

`test_catalog_file_column_stretches_to_available_dock_width` is good. Its four
explicit `sectionResizeMode` assertions pin the design decision directly, and the
growth check prints both numbers on failure. Keep it as is — it is the structural
guard, and R3 restores the behavioural one that belongs beside it.

## Note for the session log

The observation you recorded in the previous round — that a full basename does not
fit at 450 px — remains correct and is the accepted outcome. Row distinguishability
is the criterion at that width; full readability arrives around 600 px.

## Scope

R3 only. Do not begin Task 3. Gates, commit, re-mark, stop.

STATUS: CHANGES_REQUESTED
