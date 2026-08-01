# Review — ci-qt-flake-312 (round 05)

Branch: `feat/ci-qt-flake-312` @ `d6355de`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

## Verdict

CHANGES_REQUESTED — but the investigation just made its biggest step. **B9 is answered
decisively.**

## The measurement (probe run `30683970309`, 20 jobs, same commit and runner image)

| interpreter | segfaults | ordinary | unknown |
|---|---|---|---|
| **3.12** | **4 / 10** | 0 | 0 |
| **3.14** | **0 / 10** | 0 | 0 |

Full accounting, no unknowns. The only variable between the arms is the interpreter.

**The crash is genuinely Python 3.12-specific.** That is now measured, not assumed.

### Corrected pooled 3.12 baseline

| source | segfaults / runs |
|---|---|
| probe run 1 (`30683425223`) | 1 / 10 |
| probe run 2 (`30683530788`) | 1 / 10 |
| probe run 3 (`30683970309`, 3.12 arm) | 4 / 10 |
| `ci.yml` 3.12 (`30682387619`) | 1 / 2 |
| **pooled** | **7 / 32 ≈ 22%** |

Higher than the previous 13.6% estimate. Recompute the threshold:

```text
(1 - 0.219)^N < 0.01  ->  N > ln(0.01)/ln(0.781)  ->  N ≈ 19
```

So **N = 19** (2 dispatches of the 3.12 arm) confirms a fix at sub-1%, not the 32 derived
from the old rate. Update the recorded baseline and threshold.

### The `a913e04` record is now definitively wrong

That commit attributes the crash to coverage's C tracer corrupting frame state **under
Python 3.14**. Python 3.14 just returned 0/10 while 3.12 returned 4/10. Whatever
`timid = true` achieved, it was not fixing a 3.14 problem. Record this plainly — the
existing explanation would actively mislead the next reader.

## Required changes

### B11. Do not drop the probe's push trigger again

`6a8579e` expanded the matrix correctly but **removed the branch-scoped push trigger** added
in `f1bb330`, reverting `on:` to `workflow_dispatch:` only. That is exactly the round-01
blocker: a `workflow_dispatch` workflow is undispatchable until it exists on the default
branch, so with the trigger gone the probe could neither be dispatched nor fire on push.

The round was marked complete with **no probe run having executed**. The edit was made; that
it took effect was never checked.

I restored the trigger and pushed in `d6355de` to take the measurement. Keep it:

```yaml
on:
  workflow_dispatch:
  push:
    branches:
      - feat/ci-qt-flake-312
```

**Before marking any future round complete, verify the probe actually ran** — confirm a new
run id exists at your HEAD sha:

```bash
gh run list --workflow flake-probe.yml --limit 1 --json databaseId,headSha,status | head -5
```

If no run appears at your sha, the round is not complete. And **push the branch** — a
measurement that was never dispatched is not a measurement.

### B12. Task 4 — narrow the 3.12/3.14 delta, one variable per dispatch

The search space is now much smaller: what differs between CPython 3.12 and 3.14 in this
stack. Restrict the probe to the **3.12 arm only** while narrowing, to halve the cost.

In order, one per dispatch, each compared against the 22% baseline:

1. **`--no-cov` on 3.12.** Is coverage still implicated despite `timid = true`? Highest-value
   single test: if 3.12 goes clean without coverage, the interaction is confirmed as
   coverage-related *and* version-specific.
2. **Deselect the widget-heavy files** (`tests/test_actions.py`, `tests/test_main_window.py`,
   `tests/test_catalog_dock.py`, `tests/test_sql_editor.py`) on 3.12 with coverage. Does the
   crash follow them?
3. **`timid = false` on 3.12.** Quantify what `timid` actually buys on the interpreter that
   crashes — its measured benefit was only ever established on 3.14.

A single 10-sample dispatch cannot distinguish 22% from 8%, so treat each as **directional**
and say so. Reserve N = 19 for confirming a candidate fix.

A concrete suspect worth probing, not assuming: 3.12's `@dataclass(frozen=True, slots=True)`
has a known zero-arg `super()` defect — it already produced a 3.12-only `TypeError` in this
repo, fixed in `d5423e4`. The domain models are frozen and slotted and are constructed
heavily in the widget tests where the crash lands. Unproven; worth a look.

### B13. Stop after narrowing and report

Do **not** proceed into Task 5 candidate fixes in the same round. Report the three
directional rates and stop. A mitigation option is on the table that may make deep fix work
unnecessary, and that decision needs the narrowing data first.

## Constraints unchanged

Do not remove `timid = true` from the committed config (a probe-only override to measure it,
as B12.3 asks, is fine). Do not disable coverage in `ci.yml`. Do not skip, delete or xfail
tests. Do not drop either leg from `ci.yml`. Do not touch `main`. Probe triggers must remain
incapable of firing on `main` or `dev`.

## Not verified

- **No candidate fix has been tested.** Task 5 has not started.
- **Still no local reproduction** on either interpreter, including 0/20 on 3.12 where CI now
  measures ~22%. Local remains a useless predictor of CI here — do not use it to validate a
  fix.
- The 3.14 result is 10 samples. It strongly suggests a far lower rate but does not prove
  zero; at a true 5% rate, 0/10 occurs 60% of the time.

STATUS: CHANGES_REQUESTED
