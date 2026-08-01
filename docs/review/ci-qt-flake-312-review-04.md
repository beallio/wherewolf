# Review — ci-qt-flake-312 (round 04)

Branch: `feat/ci-qt-flake-312` @ `5227bcc`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

## Verdict

CHANGES_REQUESTED — **the accounting is now correct; one load-bearing assumption is not.**

Round 03's findings are fully resolved. Probe run 2 is recorded as `1 / 10` segfaults with
0 ordinary and 0 unknown; the pooled baseline is `3 / 22 ≈ 13.6%`; `N = 32` is derived
correctly from that rate; and the classifier now has an explicit `unknown` bucket plus an
accounting cross-check so an unreadable log can no longer be silently scored as
"not a crash". That was the right fix to the right problem.

**Do not start Task 4 narrowing yet.** There is a cheaper, higher-information measurement
to take first, and it may invalidate the premise narrowing would be built on.

## Required change

### B9. "3.12-only" is an unmeasured assumption — test both interpreters

This whole investigation is framed around a **Python 3.12** crash. That framing rests on
almost no data:

| evidence for "3.14 is fine" | what it actually is |
|---|---|
| CI run `30682387619`, `test (3.14)` success | **one** sample |
| CI run `30681665899`, `test (3.14)` | **cancelled** by fail-fast — no data at all |
| local 3.14, 0 crashes in 91 runs | local has **never** reproduced this crash on any interpreter |

At the measured 13.6% rate, a single clean run occurs **86% of the time by chance**. One
sample is not evidence of anything.

The local figure is actively misleading here. Local is `0 / 20` on **3.12** — the
interpreter we know crashes at ~14% on CI. So local results demonstrably do not predict CI
behaviour for 3.12, and there is no reason to believe they do for 3.14. The 0/91 number
says the crash does not reproduce locally; it says nothing about whether 3.14 crashes on a
GitHub runner.

And `.github/workflows/flake-probe.yml` **only tests 3.12** — `uv python install 3.12`,
`--python 3.12` on both the sync and the pytest step. It structurally cannot answer this.

**Change the probe matrix to cover both interpreters and dispatch once:**

```yaml
strategy:
  fail-fast: false
  matrix:
    python-version: ["3.12", "3.14"]
    probe: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
```

and thread `${{ matrix.python-version }}` through the `uv python install`, `uv sync
--python` and `uv run --python` steps. Name jobs so the interpreter is visible in the job
name (e.g. `probe-${{ matrix.python-version }}-${{ matrix.probe }}`), because your
classifier keys off job names.

That is **one dispatch, 20 jobs**, giving 10 independent samples per interpreter.

Report, using the round-03 classifier with all three buckets:

```text
3.12: segfaults C / 10   (ordinary O, unknown U)
3.14: segfaults C / 10   (ordinary O, unknown U)
```

and pool the 3.12 result with the existing 3/22.

### Why this comes before narrowing

The two outcomes lead to genuinely different work:

- **3.14 also crashes at a similar rate** → the bug is not version-specific. The "3.12-only"
  framing is wrong, and `a913e04`'s claim that `timid = true` fixed a *Python 3.14* tracer
  problem becomes doubly suspect — it would mean `timid` reduced a rate that was never
  version-bound. Narrowing should then target the Qt/coverage interaction generally.
- **3.14 is clean across 10 samples** → first real evidence for a version difference, and it
  narrows the search enormously to what differs between the two stacks.

Spending three narrowing dispatches on a premise that one dispatch can test is the wrong
order.

## After B9

Report the two rates and **stop for direction**. Do not begin Task 4 or Task 5 in the same
round. The next step depends on the answer, and a mitigation option is also on the table
that may make deep narrowing unnecessary.

## Also fix

### B10. A stale figure remains in the session log

The log still contains:

```text
Task 2: baseline probe dispatched and measured (`2 / 10`).
```

which contradicts the corrected `1 / 10`. Fix it so no superseded number survives — someone
reading this later should not have to work out which figure is current.

## Constraints unchanged

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests.
Do not drop either matrix leg from `ci.yml`. Do not touch `main`. Probe triggers must remain
incapable of firing on `main` or `dev`.

## Not verified

- **Whether 3.14 crashes on CI at all** — that is B9, and it is currently unknown.
- **No candidate fix has been tested**; Tasks 4 and 5 have not started.
- **Still no local reproduction** on either interpreter.
- The pooled 3.12 rate rests on 22 samples, so its confidence interval is wide (roughly
  3-35%). Treat 13.6% as an estimate.

STATUS: CHANGES_REQUESTED
