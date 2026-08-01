# Review — ci-qt-flake-312 (round 02)

Branch: `feat/ci-qt-flake-312` @ `5222f9a`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

## Verdict

CHANGES_REQUESTED. **The investigation is working — you got the measurement that was
missing.** Three things to fix, one of which changes the number every later comparison
depends on.

B1 from round 01 is resolved: the branch-scoped push trigger works and the probe ran.

## What you did right

- The probe dispatched and produced **real CI samples** — the thing this investigation has
  lacked from the start.
- Your **evidence lines are accurate**: you recorded that `probe-10` was
  `Fatal Python error: Segmentation fault` after `tests/test_actions.py`, and that
  `probe-9` was `RuntimeError: AppTest script run timed out after 3(s)` in
  `tests/test_app.py::test_app_initialization`. You captured the distinction correctly.
- You flagged the `a913e04` rationale mismatch without being asked twice.
- No production code, no weakened tests, `timid = true` untouched.

## Required changes

### B3. The headline baseline is wrong: 1/10 segfaults, not 2/10

Your session log headlines:

```text
Result: `crashed: 2 / 10`
```

but your own evidence directly below shows the two failures are **different bugs**:

| job | failure | is it the crash? |
|---|---|---|
| `probe-10` | `Fatal Python error: Segmentation fault`, exit 139 | **yes** |
| `probe-9` | `AppTest script run timed out after 3(s)`, exit 1 | **no** — ordinary test failure |

The `jq` you used counts `conclusion=="failure"`, which lumps native crashes together with
normal test failures. The plan is explicit that these must be distinguished, and
`scripts/check_flake.sh` already does it correctly by grepping the crash signature.

**The segfault baseline is 1/10, not 2/10.** I made exactly this mistake myself while
reviewing your work before catching it, so this is a correction, not a reprimand — but it
matters, because a fix judged against a 20% baseline needs a very different sample size
than one judged against 10%.

Fix the headline in the session log, and use a crash-aware count from now on. Something
like:

```bash
run_id=<id>
total=$(gh run view "$run_id" --json jobs --jq '[.jobs[]|select(.name|startswith("probe"))]|length')
crashes=0
for jid in $(gh run view "$run_id" --json jobs --jq '.jobs[]|select(.conclusion=="failure")|.databaseId'); do
  if gh run view --job "$jid" --log 2>/dev/null | grep -qE "Fatal Python error|Segmentation fault"; then
    crashes=$((crashes+1))
  else
    echo "  note: job $jid failed WITHOUT a crash signature (ordinary test failure)"
  fi
done
echo "segfaults: $crashes / $total"
```

**Pool the samples.** A second probe run (`30683530788`) was dispatched and was still in
flight at review time — count it the same way and report the pooled segfault rate across
both runs. Also fold in the two earlier `ci.yml` observations (1 crash in 2 runs on 3.12).
State the pooled figure as `crashes / total`, never as a bare adjective.

### B4. Recalculate the acceptance threshold from the corrected rate

The plan's "0/20 to accept a fix" was written assuming ~20%. At a **10%** rate, `0.9^20`
≈ **12%** — nowhere near good enough.

Before testing any candidate fix, state in the session log:

1. the pooled baseline rate `p` (from B3);
2. the sample size `N` you will use;
3. the resulting false-pass probability `(1 - p)^N`.

Target below ~1%. At p = 0.10 that needs roughly **N = 44**; at p = 0.17, about **N = 25**.
Since each probe dispatch yields 10 samples, that is 3-5 dispatches per candidate. If that
is too expensive, say so and propose a larger matrix rather than quietly accepting a weaker
threshold.

### B5. Use `mark-finished`, not a hand-written marker file

The round-complete marker contained the literal text `marker`, which failed validation:

```text
error: invalid round-complete marker: expected exactly two lines
       (full commit sha, then repo=<canonical-root>)
```

That aborted the supervisor. Always run:

```bash
scripts/orchestration/mark-finished ci-qt-flake-312
```

I have cleared the invalid marker. Do not write that file by hand.

## Continue the plan

Tasks 4 and 5 remain unrun. With a real baseline you can now proceed as written: **one
variable per probe dispatch**, compared against the pooled segfault rate.

The plan's stopping rule still applies, now against the corrected number: if the pooled
segfault rate turns out to be very low, stopping and documenting is a legitimate outcome.
Do not keep spending CI minutes to chase a rate you cannot measure.

## New finding to record, not to fix

`tests/test_app.py::test_app_initialization` fails intermittently on CI with
`RuntimeError: AppTest script run timed out after 3(s)`. This is a **Streamlit** test timing
out under runner load, entirely separate from the Qt segfault.

Do **not** fix it in this plan. Record it in the session log as a distinct, newly-observed
CI flake so it is not conflated with the crash, and note that the Streamlit path is removed
in Phase 14, which may make it moot. It will keep reddening CI until then.

## Constraints unchanged

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests.
Do not drop the 3.12 leg. Do not touch `main`. Keep the probe's triggers incapable of firing
on `main` or `dev`.

## Not verified

- **The pooled segfault rate is not yet established** — that is B3.
- **No candidate fix has been tested**, so nothing about a fix is verified.
- **Still no local reproduction**: 0/20 on 3.12 with coverage, on top of 0/91 on 3.14 and
  0/6 pinned to two CPUs.

STATUS: CHANGES_REQUESTED
