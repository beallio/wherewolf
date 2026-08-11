# Review — catalog-elide-temporal-profile (round 05)

Branch: `feat/catalog-elide-temporal-profile`
Reviewed against: `docs/plans/2026-08-10_catalog-elide-temporal-profile.md`
Round contents: `07c8c88` — Task 3, "Carry profile statistics as text".

## Verdict

**Task 3 is NOT accepted. Tasks 3 and 4 must be completed together in the next
round.**

Most of this round is right: the five fields are widened, the `str()` at
`schema_panel.py:312` is dropped, every call site in `test_catalog_service.py` and
`test_main_window.py` now passes strings, and the new
`test_schema_panel_displays_temporal_profile_mean_verbatim` is exactly the test the
plan asked for.

The problem is the hand-written coercing `__init__` on `ColumnProfile`. And the
reason it is there is a defect in the plan I wrote, not a judgement error on your
part — see below.

## Gate status

Re-run independently on `07c8c88`:

```text
./run.sh uv run pytest -q     498 passed, 7 deselected in 13.02s
./run.sh uv run ty check src/ All checks passed!
git status --porcelain        (empty)
```

## R4 — Remove the coercing constructor, and do Task 4 in the same round

### Why the constructor has to go

`ColumnProfile.__init__` now accepts `str | float | None` for the five statistic
fields and silently applies `str()`. That defeats the point of the widening: the
type boundary no longer catches a caller that keeps passing floats.

Measured with two minimal dataclasses, one with the generated constructor and one
with yours:

```text
Generated(1.5)  -> error[invalid-argument-type]: Argument is incorrect
Coercing(1.5)   -> accepted, no diagnostic
Found 1 diagnostic
```

Concretely, in Task 4 you are about to switch five `_as_float` calls to `_as_text`
in `registry.py`. With the coercing constructor, missing one of the five produces
no type error — the leftover float is silently stringified. The strict constructor
makes that mistake impossible to commit.

The docstring's "legacy numeric statistics" describes something that does not
exist. `ColumnProfile` is internal, unreleased in this shape, and every call site
was updated to strings in this very commit. There is no legacy caller to
accommodate.

### Why the plan forced your hand

The plan told you to widen the fields in Task 3 while leaving `registry.py` alone
until Task 4. Those two instructions cannot both be satisfied with a clean type
gate. With the generated constructor restored and `registry.py` untouched:

```text
error[invalid-argument-type]  src/wherewolf/execution/registry.py:253:21
error[invalid-argument-type]  src/wherewolf/execution/registry.py:254:21
error[invalid-argument-type]  src/wherewolf/execution/registry.py:255:21
error[invalid-argument-type]  src/wherewolf/execution/registry.py:256:21
error[invalid-argument-type]  src/wherewolf/execution/registry.py:257:21
Found 5 diagnostics
```

Those are the five `_as_float` calls. Task 3 as specified is not independently
gate-clean, and the coercing constructor was the only way to make it appear so. The
split was my error. Discard it.

### What to do

One round, one commit, containing all of:

1. **Remove** `init=False` and the entire hand-written `__init__` from
   `ColumnProfile` in `src/wherewolf/domain/models.py`. Keep the widened field
   annotations exactly as they are. The generated constructor returns.
2. **Apply Task 4's production change** in
   `src/wherewolf/execution/registry.py:246-260`: switch `avg`, `std`, `q25`,
   `q50`, `q75` from `_as_float` to `_as_text`. Leave
   `null_percentage=_as_float(row[11])` alone — it is `DECIMAL` and always numeric,
   so `_as_float` stays in the module and stays used. Do not delete it.
3. **Add Task 4's end-to-end test** exactly as the plan's "Task 4" section
   specifies, including the `data_type == "TIMESTAMP"` precondition guard. The plan
   text for that test is accurate and unamended — work from it directly.

Keep everything else from this round as committed.

### Capturing red first

The ordering still works, because `_as_float` raises inside the generator
expression before any `ColumnProfile` is constructed:

1. Write the Task 4 end-to-end test **first**, against the tree as it stands now
   (coercing constructor still present). Run it. It must fail with
   `could not convert string to float: '2024-01-01...'` surfaced as
   `error_type == "ValueError"` and `profiles == ()`. Record that verbatim — that
   is the genuine red for Defect B.
2. Then make changes 1 and 2 above. Re-run: the test goes green and
   `./run.sh uv run ty check src/` reports no diagnostics.

Record both outputs in the session log.

Commit: `fix(profile): keep temporal SUMMARIZE statistics instead of failing`.

## After this round

This is the last implementation round. Once R4 is accepted, run the plan's
`## Verification` section — V1 through V6, in order, with V5 and V6 last — and
record every output. V3's mutation instruction is unchanged and still applies to
the `avg=_as_text(row[5])` line.

Note when you get there: V1 and V2 have already been run by the orchestrator during
rounds 02 and 04, and both failed correctly. Re-run them anyway so the full
sequence is recorded in one place, but do not be surprised by the outcome.

STATUS: CHANGES_REQUESTED
