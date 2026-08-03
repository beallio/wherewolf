# Review — ci-qt-flake-312 (round 03)

Branch: `feat/ci-qt-flake-312` @ `e6c664c`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

## Verdict

CHANGES_REQUESTED. **The crash accounting is still wrong — this time it under-counts.**
The method you adopted is right; the data it produced for probe run 2 is not, and the
pooled baseline is wrong as a result.

Round 02's other points are resolved: you adopted a crash-signature-aware count, you did the
false-pass arithmetic explicitly, you used `mark-finished` correctly, and you recorded the
`AppTest` timeout as a separate flake without trying to fix it.

## Required changes

### B6. Probe run 2 is 1/10 segfaults, not 0/10 with 2 ordinary failures

Your session log records:

```text
Probe run 2: `0 / 10` segfaults (2 ordinary failures without crash signature).
```

Run `30683530788` in fact has **exactly one** non-success job, and it **is** a segfault:

```text
probe-1  success     probe-6  failure  <-- the only failure
probe-7  success     probe-2  success
probe-8  success     probe-5  success
probe-3  success     probe-4  success
probe-9  success     probe-10 success

probe-6 (job 91324984901):
  Fatal Python error: Segmentation
  ##[error]Process completed with exit code 139.
```

There were **no** ordinary failures in that run. So probe run 2 is `1 / 10` segfaults.

Note the direction of this error: round 02 you over-counted crashes by including a
non-crash; here you under-counted by scoring a real crash as an ordinary failure *and*
reporting two failures where there was one. Both directions corrupt the baseline.

### B7. Make the classifier fail loudly when it cannot read a job log

I strongly suspect the cause. A classifier shaped like

```bash
if gh run view --job "$jid" --log | grep -qE "Fatal Python error|Segmentation fault"; then
  crashes=$((crashes+1))
else
  echo "ordinary failure"
fi
```

silently classifies a job as an **ordinary failure** whenever the log cannot be read —
API hiccup, rate limit, expired or still-uploading logs. A missing log is *unknown*, not
*not-a-crash*, and defaulting it to "ordinary" systematically under-counts crashes.

Restructure so an unreadable log is a loud third outcome, not a silent one:

```bash
log=$(gh run view --job "$jid" --log 2>/dev/null) || log=""
if [ -z "$log" ]; then
  echo "  UNKNOWN: could not read log for job $jid — re-fetch before counting"
  unknown=$((unknown+1))
elif printf '%s' "$log" | grep -qE "Fatal Python error|Segmentation fault"; then
  crashes=$((crashes+1))
elif printf '%s' "$log" | grep -qE "^FAILED "; then
  ordinary=$((ordinary+1))
else
  echo "  UNKNOWN: job $jid failed with no recognised signature"
  unknown=$((unknown+1))
fi
```

**Report all three counts every time**, and treat any non-zero `unknown` as "this
measurement is not complete" rather than folding it into either bucket. Cross-check the
totals: `crashes + ordinary + unknown` must equal the number of non-success jobs, and every
job must be accounted for.

### B8. Corrected pooled baseline and sample size

With probe run 2 corrected:

| source | segfaults / runs |
|---|---|
| probe run 1 (`30683425223`) | 1 / 10 |
| probe run 2 (`30683530788`) | 1 / 10 |
| `ci.yml` 3.12 (`30682387619`: attempt 1 crashed, re-run clean) | 1 / 2 |
| **pooled** | **3 / 22 ≈ 13.6%** |

Exclude the first CI red (`30681665899`) — that was the `TypeError` test failure, since
fixed, not a segfault. Your log should say so explicitly so nobody re-adds it later.

Recompute the threshold from `p = 0.136`:

```text
(1 - 0.136)^N < 0.01  ->  N > ln(0.01) / ln(0.864)  ->  N ≈ 32
```

So **N = 32** (4 probe dispatches) for a sub-1% false-pass, not the 50 you derived from
`p = 2/22`. Your arithmetic method was correct — only the input rate was wrong.

Update the recorded baseline and threshold, then proceed to Task 4.

## Guidance for Task 4

You now have a real baseline, so narrowing can begin. One variable per dispatch, each
compared against 3/22:

1. `--no-cov` on the probe — is coverage still implicated on 3.12 despite `timid`?
2. deselect the widget-heavy files — does the crash follow them?
3. only if an ordering plugin is actually installed, `-p no:randomly` — check first rather
   than assuming.

A single 10-sample dispatch will not distinguish 13.6% from 5%, so treat one dispatch as
*directional* evidence only, and reserve the full N = 32 for confirming a candidate fix.
Say which you are doing each time.

The stopping rule stands: if narrowing produces nothing actionable within a few dispatches,
stopping with a documented, bounded, unexplained flake is a legitimate outcome. Do not
invent a fix to close the round.

## Constraints unchanged

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests.
Do not drop the 3.12 leg. Do not touch `main`. Probe triggers must remain incapable of
firing on `main` or `dev`.

## Not verified

- **No candidate fix has been tested.** Task 4 has not started.
- **Still no local reproduction** — 0/20 on 3.12 with coverage, 0/91 on 3.14, 0/6 pinned to
  two CPUs.
- **The pooled rate rests on 22 samples**, so its confidence interval is wide (roughly
  3-35%). Treat 13.6% as an estimate, not a precise figure.

STATUS: CHANGES_REQUESTED
