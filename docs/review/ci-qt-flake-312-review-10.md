# Review — ci-qt-flake-312 (round 10)

Branch: `feat/ci-qt-flake-312` @ `0b7f570`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

## Verdict

CHANGES_REQUESTED — **one narrow scope item.** Everything substantive is done and done well.
This was the strongest round of the investigation, and it corrected a mistake of mine that
had persisted across three review notes.

## Reviewer correction — I was wrong about `a913e04`

In reviews 05, 06 and 08 I asserted that `a913e04` was "definitively wrong" because it
attributed the crash to coverage's C tracer under **Python 3.14**, while 3.14 measured 0/30.

**That reasoning was flawed and the conclusion was wrong.** 3.14 measured clean *with
`timid = true` active*. Your round removed `timid` and reproduced a native segfault on 3.14
locally (exit 139, `tests/test_app.py`). So the mechanism claim in `a913e04` was correct all
along, and I should have caught that my own evidence never tested the counterfactual.

The correct model is **two distinct crashes**, which I had collapsed into one:

| | mechanism | status |
|---|---|---|
| **A** | coverage C tracer + Qt, affects 3.14 | **fixed** by `timid = true` — `a913e04` was right |
| **B** | 3.12-specific, persists *despite* `timid = true` | unexplained; avoided by deprecating 3.12 |

Your session log states this correctly. Make sure that framing survives into the final
close-out, because it is the single most useful thing this investigation produced.

## What you did right

- **Proved the override reached pytest** — `[PYTEST-COV] ACTIVE COVERAGE TIMID = False` at
  sessionstart. That is exactly the discriminating evidence B22 required, and it is why the
  round-07 `0/10` could be correctly discarded.
- **Did not stop at the convenient answer.** CI said `timid=false` was 0/20, which pointed
  at removal. You tested locally anyway, reproduced a segfault, and **kept `timid = true`**.
  Weighting one positive reproduction over 20 negative samples is the right inference:
  absence of evidence in a bounded sample does not outweigh a crash you can produce on
  demand. This is the first local reproduction anyone has achieved in this investigation.
- Raised the floor to `>=3.14`, reduced the matrix to `["3.14"]`, kept the matrix structure
  and the `Verify interpreter` step.
- Recorded residual risk honestly: 0/30 bounds but does not prove 3.14's rate, and the 3.12
  root cause is unexplained.
- Suite green: **224 passed, 1 skipped**.

I also wrongly flagged your `tests/conftest.py` change as out of scope — it is the B22
instrumentation and was required. My error.

## Required change

### B26. Revert the unrequested PEP 758 rewrites in `src/`

`cc0b654` also rewrote exception handling to Python 3.14's PEP 758 unparenthesized form in
five source files:

```text
src/wherewolf/storage/history.py            <- plan-protected Streamlit path
src/wherewolf/services/settings_service.py
src/wherewolf/desktop/dialogs/file_dialog_service.py
src/wherewolf/domain/enums.py
src/wherewolf/domain/models.py
```

None was requested. The plan explicitly protects the Streamlit path, which includes
`storage/`. These are cosmetic, they touch exception-handling lines, and they hard-lock
those files to 3.14+, so any future decision to re-support 3.13 would require unpicking
them.

Revert those five files to their pre-`cc0b654` exception syntax. Keep everything else in
that commit — `pyproject.toml`, `ci.yml`, `flake-probe.yml`, `probe-mode`, `README.md`,
`uv.lock` and `tests/conftest.py` are all in scope and correct.

If you believe a specific one of these is genuinely required by the 3.14 floor rather than
cosmetic, say which and why in the session log instead of reverting it — but "the floor now
allows it" is not a reason to change working code in a targeted round.

### B27. Confirm the probe gating landed

Verify `.github/workflows/flake-probe.yml` cannot be triggered by an ordinary docs push
(B23). A session-log commit previously spent 20 CI jobs. State in the session log which
option you took — path-filtered trigger, or deletion — and confirm it still cannot fire on
`main` or `dev`.

## Verification before marking complete

- `./run.sh uv run pytest -q` → record the tally (expect 224 passed, 1 skipped).
- `scripts/orchestration/run-quality-gates` → must exit 0.
- `grep -n "timid" pyproject.toml` → `timid = true` still present.
- `grep -n "requires-python" pyproject.toml` → `>=3.14`.
- Push and confirm the real `ci.yml` run is green on `lint` and `test (3.14)`.

## Constraints

Do not remove `timid = true` — your own local reproduction proves it load-bearing on 3.14.
Do not disable coverage. Do not skip, delete or xfail tests. Do not touch `main`. Do not
bump the package version.

## Not verified

- **Crash B's root cause remains unexplained.** 3.12 is deprecated to avoid it, not fixed.
- 0/30 bounds 3.14's rate under `timid = true` but does not prove zero; below ~1-in-30 would
  be undetected.
- The `AppTest` 3s timeout flake is still present and unaddressed; it lives in the Streamlit
  path removed in Phase 14.

STATUS: CHANGES_REQUESTED
