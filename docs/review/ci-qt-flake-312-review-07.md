# Review — ci-qt-flake-312 (round 07)

Branch: `feat/ci-qt-flake-312` @ `1fb7d0e`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

## Verdict

CHANGES_REQUESTED — **one focused task.** This round did what six previous rounds could not:
it actually dispatched probes and produced narrowing data. Good work. But one of the three
results is not yet trustworthy, and it happens to be the one that would rewrite the story.

## What you did right

- Made the probe mode a committed file so the branch-scoped push trigger can reach it (B14).
- **Pushed and verified a run existed at your HEAD sha** on every dispatch (B15). Three
  prior rounds silently failed here.
- Ran all three narrowing modes and recorded them as directional, as asked.
- Correctly kept the crash separate from the `AppTest` timeout.

## Results so far (each 10 samples, directional)

| mode | segfaults | note |
|---|---|---|
| baseline (coverage + all tests) | 7/32 ≈ 22% | pooled across earlier runs |
| `no-cov` | 0/10 | |
| `deselect` widget tests | 0/10 | 1 ordinary `AppTest` timeout |
| `timid-false` | 0/10 | **suspect — see B18** |

At a true 22% rate, a single 0/10 happens ~8% of the time, so none of these is conclusive
alone. But `no-cov` and `deselect` both pointing to zero is consistent with the crash
requiring **coverage and the Qt widget tests together**.

## Required change

### B18. Prove the `timid-false` override actually reached pytest

`timid = false` restores coverage's C tracer — the configuration `a913e04` claims *causes*
the crash. It measured **0/10**. Before that number can mean anything, we must know the
override took effect.

I could not confirm it. The job log shows the literal script text
`--cov-config=/tmp/wherewolf/coverage-no-timid.ini`, which is the case-statement source, not
the expanded pytest command line. Job durations are uninformative: baseline 3.12 median 66s
vs timid-false 61s, dominated by apt/uv/java setup, so a ~10s difference in test runtime is
invisible.

**Add positive proof to the probe run itself**, then re-dispatch `timid-false`. Make the job
print, before pytest starts:

1. the **fully expanded** pytest argv (e.g. `printf '%q ' "${args[@]}"` or `set -x` around
   the invocation), so the `--cov-config` flag is visibly present in the real command;
2. the **effective** coverage setting as coverage itself reports it, not as the file claims.
   For example:

   ```bash
   ./run.sh uv run --python 3.12 python -c \
     "import coverage; c=coverage.Coverage(config_file='/tmp/wherewolf/coverage-no-timid.ini'); \
      c._init(); print('EFFECTIVE timid =', c.config.timid)"
   ```

   Adapt as needed — the requirement is that the run prints coverage's *resolved* `timid`
   value, not the contents of an ini file.

3. As a cross-check, do the same in `baseline` mode and confirm it prints `True`. A proof
   that cannot distinguish the two modes proves nothing.

Then re-run `timid-false` (10 samples) and report the rate **alongside** the printed
effective value.

### Why this matters more than it looks

Two outcomes, both significant:

- **Override applied and 0/10 is real** → `timid = true` is not what suppresses the crash.
  `a913e04` is then wrong twice: wrong about the interpreter (it blames 3.14, which measures
  0/10) *and* wrong about the mechanism. It would also mean the 0/91 local sweep that
  "confirmed" that fix proved nothing, because it ran on 3.14 where the crash never occurs.
  And we are paying ~1.7x CI runtime for a setting that may buy nothing.
- **Override did not apply** → the 0/10 is an artefact, `timid` remains a live candidate,
  and the narrowing table needs that row struck out.

Either way the session log must end up saying which, with the evidence attached.

## Do not do yet

Do not attempt a fix, and do not change `timid = true` in committed config. This round is
**one dispatch plus proof**. Report and stop.

## Constraints

Do not disable coverage in `ci.yml`. Do not skip, delete or xfail tests. Do not drop either
leg from `ci.yml`. Do not touch `main`. Probe triggers must remain incapable of firing on
`main` or `dev`. Keep counting with the three-way classifier — crash / ordinary / unknown,
where an unreadable log is `unknown` and invalidates the count until re-fetched. Note that a
transient log-read failure already produced one spurious `unknown` this round, which on
retry turned out to be an ordinary `AppTest` timeout.

## Not verified

- **Whether `timid` does anything on 3.12** — that is B18, and it is currently unknown.
- **No candidate fix has been tested.**
- Every narrowing rate rests on 10 samples and cannot distinguish 22% from 8%.
- Still no local reproduction on either interpreter.

STATUS: CHANGES_REQUESTED
