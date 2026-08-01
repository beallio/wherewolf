# Review — ci-qt-flake-312 (round 08)

Branch: `feat/ci-qt-flake-312` @ `2464e95`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

## Verdict

CHANGES_REQUESTED — **direction change from the maintainer.** One dispatch, one question.

The maintainer has decided the likely resolution is to **deprecate Python 3.12** rather than
fix or mitigate the crash. The crash is confined to the test suite under pytest + coverage +
Qt widget tests; the application itself is not implicated. Wherewolf is a desktop app
installed via `uv tool install`, which provisions its own interpreter, so raising the floor
costs its users very little.

Before that happens, one thing must be confirmed. **This supersedes B18 — do not spend
further effort proving the `timid` override.**

## Required change

### B19. Confirm Python 3.14 is genuinely clean, with 20+ samples

The case for dropping 3.12 rests on 3.14 being sound. Current evidence for that is **10
samples** (probe `30683970309`, 3.14 arm: 0/10).

That is not enough to move to it. At a true 5% crash rate, 0/10 occurs about **60%** of the
time. Deprecating 3.12 on the strength of it risks trading a *measured-crashy* interpreter
for an *under-measured* one — and retiring the probe that could have told us.

Do this:

1. Set the probe matrix to **`python-version: ["3.14"]`** and `probe: [1..20]` — 20 samples
   in one dispatch.
2. Set `.github/probe-mode` to `baseline` (coverage on, `timid = true`, full suite) so it
   matches the configuration `ci.yml` actually runs.
3. Push, and **verify a run exists at your HEAD sha** before treating the round as done.
4. Count with the three-way classifier — crash / ordinary / unknown. Re-fetch any `unknown`
   before reporting; a transient log-read failure already produced one spurious `unknown`
   earlier in this investigation, which on retry proved to be an ordinary `AppTest` timeout.

Report as `segfaults C / 20 (ordinary O, unknown U)`.

**Decision rule, stated in advance:**

- **0 / 20** → 3.14 is clean enough to standardise on. `(1 - 0.22)^20 ≈ 0.7%`, so if 3.14
  shared 3.12's ~22% rate we would almost certainly have seen it. Proceed to deprecation.
- **1 or more crashes** → the bug is **not** version-bound. Deprecating 3.12 would have
  hidden it rather than solved it. Stop and report; the decision needs revisiting.

### B20. Report and stop

Do **not** change `requires-python`, do **not** touch the `ci.yml` matrix, and do **not**
remove `timid = true` in this round. Those follow the result, not precede it.

Note in the session log that B18 was superseded, so a later reader understands why the
`timid` override proof was left unfinished. `2464e95` added the instrumentation but no probe
was ever dispatched with it, so the effective `timid` value is still unknown — record that
as an open question rather than implying it was answered.

## Context for whoever reads this later

Established by measurement across this investigation:

| fact | evidence |
|---|---|
| Native segfault (exit 139) at ~2%, after `tests/test_actions.py` | multiple CI logs |
| **Python 3.12-specific** | 3.12 → 4/10, 3.14 → 0/10, same commit and runner |
| Pooled 3.12 rate | 7/32 ≈ 22% |
| `no-cov` on 3.12 | 0/10 (directional) |
| deselect widget tests on 3.12 | 0/10 (directional) |
| `timid-false` on 3.12 | 0/10 — **unverified**, override never proven to apply |
| Never reproduces locally | 0/20 on 3.12, 0/91 on 3.14, 0/6 pinned to 2 CPUs |
| Second unrelated flake | Streamlit `AppTest` 3s timeout — do not conflate |

`a913e04` attributes the crash to coverage's C tracer under **Python 3.14**, the interpreter
that measures 0/10. That explanation is wrong and should be corrected in the session log
whenever this investigation closes.

## Constraints

Do not disable coverage. Do not skip, delete or xfail tests. Do not touch `main`. Probe
triggers must remain incapable of firing on `main` or `dev`.

## Not verified

- **Whether 3.14 is clean beyond 10 samples** — that is this round.
- Whether `timid = true` does anything on 3.12.
- No candidate fix has been tested; none is planned under the current direction.

STATUS: CHANGES_REQUESTED
