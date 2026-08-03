# Review — ci-qt-flake-312 (round 01)

Branch: `feat/ci-qt-flake-312`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

> **Note on this file.** An empty template of this note was committed in `61b66b5` while the
> round was still in progress — my mistake as orchestrator, not the implementer's. The
> implementer behaved correctly: the protocol instructs it to commit any uncommitted review
> note it finds. This revision replaces the placeholder with the real review. Nothing was
> deleted.

## Verdict

CHANGES_REQUESTED — **the plan blocked you, not your work.** Tasks 1 and 2 were executed
correctly, and you were right to stop rather than fabricate CI numbers. One concrete change
unblocks the investigation.

## What you did right

- **Task 1** measured the local 3.12 + coverage baseline at **0 / 20** with the exact
  environment isolation specified, using `--color=no` and counting only native crash
  signatures.
- You **did not enter Task 3**, because local bisection is meaningless without a local
  reproduction. Correct.
- **Task 2** built the probe to spec: 10-job matrix on 3.12, `fail-fast: false`,
  CI-identical setup, manual trigger only.
- When dispatch failed you **reported the blocker verbatim and stopped**, instead of
  inventing probe samples. This whole investigation turns on trustworthy measurements, so
  that was the right call and it is why this review is short.

## Required changes

### B1. The probe cannot be dispatched from a feature branch — my plan caused this

Your diagnosis is correct; I reproduced it exactly:

```text
HTTP 404: workflow flake-probe.yml not found on the default branch
```

GitHub only exposes a `workflow_dispatch` workflow once it exists on the repository's
**default branch**, which here is `main`. The probe lives only on
`feat/ci-qt-flake-312`, so it is undispatchable. The branch is pushed and visible; that is
not the problem.

Plan Verification V2 demanded the `on:` block contain **only** `workflow_dispatch`,
precisely so the probe could never fire on ordinary pushes. That constraint is what makes it
unusable here. **The plan was wrong; this is not a failure on your part.**

Change `.github/workflows/flake-probe.yml` to trigger on push, scoped to this investigation
branch only, keeping `workflow_dispatch` for later:

```yaml
on:
  workflow_dispatch:
  push:
    branches: [ feat/ci-qt-flake-312 ]
```

A push-triggered workflow runs from the pushed branch's own copy, so the default-branch
requirement does not apply. Branch-scoping preserves what I actually wanted: it can never
fire on `main` or `dev`, nor on any other feature branch.

**Revised rule, superseding plan V2:** the probe's `on:` block must contain no trigger that
can fire on `main` or `dev`. `push` limited to `feat/ci-qt-flake-312` satisfies that.

Then get the measurement the plan needs:

1. push the branch to run the 10-job probe;
2. count crashed jobs:

   ```bash
   gh run list --workflow flake-probe.yml --limit 1
   gh run view <id> --json jobs \
     --jq '[.jobs[]|select(.name|startswith("probe"))] | "crashed: \([.[]|select(.conclusion=="failure")]|length) / \(length)"'
   ```

3. confirm at least one failure is a genuine segfault after the widget tests, not an
   unrelated failure:

   ```bash
   gh run view <id> --log-failed | grep -E "Fatal Python error|Segmentation fault|^tests/" | head -20
   ```

4. record the fraction in the session log — **this is the baseline every later measurement
   is compared against.**

Then continue with Tasks 4 and 5 as written. The plan's stopping rule is unchanged: **if the
probe shows 0/10, push once more for 20 total samples; if still 0/20, stop and report.**
Chasing a sub-5% CI-only crash is not worth further CI minutes, and that is a legitimate
outcome.

### B2. Tasks 6 and 7 were completed against work that had not happened

`9b81104` closes out the investigation and Task 6 retains the probe, but Tasks 4 and 5 were
never run. Your session log is honest about this — it states plainly that no CI baseline was
obtained and no fixes were attempted, which is good — but the round is not finished.

After B1, rewrite both:

- Task 4/5 sections must record the **actual** probe rates, one variable per dispatch;
- the Task 7 close-out must state the measured CI rate, or, if the stopping rule fires, that
  the rate is below the probe's detection threshold and the cause remains unknown.

Also complete the correction the plan asked for: `a913e04`'s message attributes the crash to
coverage's C tracer under **Python 3.14**, but 3.14 passes and 3.12 crashes. Do not rewrite
that commit — record in the session log what is now known and what that explanation got
wrong.

## Constraints unchanged

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests.
Do not drop the 3.12 leg from `ci.yml`. Do not touch `main`.

## Not verified

- **No CI rate exists yet.** The crash's frequency is unmeasured; one observed CI failure
  plus one passing re-run bounds it only very loosely.
- **Never reproduced locally** — 0/20 on 3.12 with coverage this round, on top of 0/91 on
  3.14 and 0/6 pinned to two CPUs previously.
- No fix was attempted, so nothing about a fix has been verified.

STATUS: CHANGES_REQUESTED
