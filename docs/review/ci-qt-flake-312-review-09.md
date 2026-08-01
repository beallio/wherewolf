# Review — ci-qt-flake-312 (round 09)

Branch: `feat/ci-qt-flake-312` @ `69d7ba4`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

## Verdict

CHANGES_REQUESTED — **closing round.** The investigation is finished and the maintainer has
made the call. This round implements it. No further measurement of the crash itself.

B19 is satisfied: **3.14 measured 0 segfaults / 20** in `baseline` mode (coverage on,
`timid = true`, full suite), with 0 ordinary and 0 unknown across 20 distinct jobs. Pooled
3.14 evidence is now **0/30** against 3.12's **7/32 ≈ 22%**. If 3.14 shared that rate, 0/30
would occur roughly 0.06% of the time.

**Decision: deprecate Python 3.12.** The crash is confined to the test suite under
pytest + coverage + Qt widget tests; the application is not implicated. Wherewolf installs
via `uv tool install`, which provisions its own interpreter, so raising the floor costs
users very little.

## Required changes

### B21. Raise the floor to 3.14

1. `pyproject.toml`: `requires-python = ">=3.14"`. `.python-version` is already `3.14`.
2. Re-lock: `./run.sh uv lock`, then `./run.sh uv sync --all-extras --dev`.
3. `.github/workflows/ci.yml`: drop `3.12` from the `test` matrix, leaving
   `python-version: ["3.14"]`. **Keep the matrix structure** — do not flatten it to a single
   job; future versions get added back here.
4. Keep the `Verify interpreter` step. It has already caught a real defect and must survive.

### B22. Measure whether `timid = true` is still needed, then decide

With 3.12 gone, `timid = true` may be buying nothing while costing ~1.7x runtime (local
suite ~24s vs ~14s). Its stated justification in `a913e04` names Python **3.14** as the
crashing interpreter, which is now known to be wrong, so the setting has no verified
rationale left.

**Measure before removing.** Set the probe to 3.14, `probe: [1..20]`, and a mode that runs
with `timid = false`:

- **0 / 20 with `timid = false`** → remove `timid = true` from `pyproject.toml` and record
  the measurement as the justification. `(1 - 0.22)^20 ≈ 0.7%`, and 3.14 baseline is already
  0/30, so this is a like-for-like comparison.
- **≥ 1 crash** → keep `timid = true`, and record that it *is* load-bearing on 3.14 after
  all — which would be a genuinely new finding worth stating clearly.

You must also **prove the override reached pytest** this time. The earlier `timid-false`
result was discarded because it could not be verified. `2464e95` added instrumentation but
no probe was ever dispatched with it. Print coverage's **resolved** `timid` value at
runtime, and print it in the comparison run too so the check is shown able to distinguish
`True` from `False`. A proof that cannot tell the two apart proves nothing.

If you cannot demonstrate the override applies, **keep `timid = true`** and say why — do not
remove a setting on the strength of an unverifiable measurement.

### B23. Stop the probe firing on every push

A docs-only commit (`69d7ba4`, a session-log update) triggered a full 20-job probe run
(`30686036375`). Every routine push to this branch costs a full matrix.

Gate it. Either restrict the push trigger to the mode file:

```yaml
push:
  branches:
    - feat/ci-qt-flake-312
  paths:
    - .github/probe-mode
    - .github/workflows/flake-probe.yml
```

or delete the workflow now that the investigation is closing. **State which you chose and
why in the session log.** If you keep it, it must remain incapable of firing on `main` or
`dev`.

### B24. Update the documentation

- `README.md`: state the Python requirement is now **3.14+**. Bump the `cacheBuster` query
  parameter on README image/badge URLs per `AGENTS.md` Section 13.
- Note the raised floor as a user-visible change; it belongs in release notes when 0.6.0
  ships.

### B25. Correct the record

The session log must end with an accurate account. Include:

1. **The measured outcome**: 3.12 ≈ 22% (7/32), 3.14 0/30, and that the root cause is
   **unexplained** — 3.12 is deprecated to avoid the crash, not because it was fixed.
2. **`a913e04` is wrong.** It attributes the crash to coverage's C tracer under Python
   **3.14** — the interpreter measuring 0/30. Do not rewrite that commit; correct it here.
3. **The `timid` override was never proven to apply** in round 07, which is why that
   `0/10` result was discarded. Record the B22 outcome as the authoritative answer.
4. **The residual risk**: 0/30 bounds 3.14's rate but does not prove zero. A rate below
   roughly 1-in-30 would not have been detected. If the defect is a latent Qt-teardown
   problem that 3.12 merely made likely, it could resurface. Say so plainly.
5. **The second flake**: `tests/test_app.py::test_app_initialization` intermittently fails
   with `AppTest script run timed out after 3(s)`. Unrelated to the segfault, still present,
   in the Streamlit path removed in Phase 14. Not fixed here.
6. **Directional narrowing results**, labelled as directional: `no-cov` 0/10 and `deselect`
   widget tests 0/10 on 3.12, both consistent with the crash requiring coverage *and* the Qt
   widget tests together.

## Verification for this round

- `./run.sh uv run pytest -q` on 3.14 — expect **224 passed, 1 skipped** or higher, and
  record the tally.
- `scripts/orchestration/run-quality-gates` must exit 0.
- `grep -n "requires-python" pyproject.toml` shows `>=3.14`.
- `ci.yml` matrix contains only `3.14`, and the `Verify interpreter` step is intact.
- Push and confirm the **real** `ci.yml` run is green on `lint` and `test (3.14)`.
- `scripts/check_flake.sh 25` locally — expect 0 native crashes.

## Constraints

Do not disable coverage. Do not skip, delete or xfail tests. Do not touch `main`. Do not
bump the package version — the 0.6.0 bump belongs to the final cutover plan.

STATUS: CHANGES_REQUESTED
