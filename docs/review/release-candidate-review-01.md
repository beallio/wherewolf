# Review — release-candidate (round 01)

Branch: `feat/release-candidate` @ `c50bbd8`
Reviewed against: `docs/plans/2026-08-01_release-candidate.md`

## Verdict

CHANGES_REQUESTED — **one defect: the new `qt-smoke` job makes the entire workflow invalid, so
no CI runs at all.** Everything else in this round is correct, including both distribution exit
criteria, which I verified against the built artifacts.

## K1. `runner` context is not available in job-level `env:`

`.github/workflows/ci.yml:138-142`, in the `qt-smoke` job:

```yaml
    env:
      UV_PROJECT_ENVIRONMENT: ${{ runner.temp }}/wherewolf-venv
      UV_CACHE_DIR: ${{ runner.temp }}/wherewolf-uv-cache
      XDG_CACHE_HOME: ${{ runner.temp }}/wherewolf-cache
      PYTHONPYCACHEPREFIX: ${{ runner.temp }}/wherewolf-pycache
      TMPDIR: ${{ runner.temp }}
```

The **`runner` context does not exist at job level.** It is available in step contexts
(`steps.*.env`, `steps.*.if`, `steps.*.run`) but not in `jobs.<id>.env`. GitHub rejects the
workflow at parse time.

**The evidence this actually broke everything:**

```text
run 30731006869: event=push  conclusion=failure  jobs=0  duration=0s  path=.github/workflows/ci.yml
gh run view --log      → "log not found"
gh pr checks 11        → "no checks reported"
```

A zero-second failure with **zero jobs and no logs**, plus a run created for a push to a branch
the triggers exclude, is GitHub reporting a workflow it could not parse. **No lint, no tests, no
build, no cross-platform job has run on this branch.** The YAML is locally valid — `yaml.safe_load`
parses it and lists all five jobs — so this is only visible server-side.

Your other two uses are correct and should stay: `if: runner.os == 'Linux'` (line 153) and
`${{ runner.temp }}` inside a step `run:` (line 162) are both step-level.

**Fix:** move those five variables to step-level `env:` on the steps that need them, or use a
context valid at job level — `${{ github.workspace }}` works — or rely on the `RUNNER_TEMP`
environment variable from within `run:` blocks. Whichever you choose, **push and confirm the
workflow actually schedules jobs**; a green local YAML parse does not prove GitHub accepts it.

This is the fourth CI-only failure this session, and the same root pattern: *local verification
cannot reproduce what CI does*. It is also why this phase went to a PR instead of a direct
merge — `dev` is untouched and still green.

## Everything else is correct

### The hard boundary held

```text
version = "0.5.2"          # unchanged
git tag --points-at HEAD   # empty
```

No version bump, no tag, no `main` change. Eleven commits, one per task.

### Both distribution exit criteria — verified by review against the artifacts

I built the wheel and sdist myself and inspected the archives rather than `pyproject.toml`:

| check | result |
|---|---|
| license in **wheel** | `dist-info/licenses/LICENSE`, `dist-info/licenses/LICENSES/MIT-pre-0.6.txt` |
| license in **sdist** | `LICENSE`, `LICENSES/MIT-pre-0.6.txt` |
| wheel metadata | `License-Expression: GPL-3.0-only` + both `License-File` entries |
| clean-env install | fresh venv (not the project venv); `MainWindow` constructs offscreen |
| default install | **no pyspark, no streamlit** |

That last row is Phase 13's and Phase 14's exit criteria holding in the actually-distributed
artifact, and the MIT-pre-0.6 notice satisfies criterion 21.9 about preserving pre-cutover terms.

### The per-leg audit test is real

I mutated the DuckDB leg to install the spark extra:

```text
FAILED tests/test_ci_workflow.py::test_ci_install_contracts_match_the_tooling_each_leg_runs
FAILED tests/test_ci_spark_tiers.py::test_ci_has_separate_duckdb_only_and_opt_in_spark_tiers
```

Both bite. That guard is exactly what would have caught the `lint` breakage two phases ago, and
it asserts properties rather than literal command strings, as asked.

### Other measurements

| check | result |
|---|---|
| gates (3.14) | 354 passed, 7 deselected |
| **V10** crash gate 25 + 25 | **0 native crashes / 50** |
| `--locked` reintroduced? | no — correctly absent |

The `qt-smoke` job's *design* is right: three OSes with `fail-fast: false`, `uv` invoked directly
rather than `./run.sh` on Windows, apt gated to Linux, and it runs the real end-to-end DuckDB
flow rather than a bare import. Only the context bug prevents it from running.

## Verification before marking complete

- Fix K1, push, and **confirm from a real run** that jobs are scheduled — paste the per-OS
  conclusions for `qt-smoke`. This is V4 and it cannot be satisfied locally.
- Confirm `build` and the other legs pass in that same run.
- `git status --short` → empty; version still `0.5.2`; no tag.

**Already measured by review — do not re-run:** the packaging inspection, the clean-env install,
the per-leg mutation, and the crash gate (0/50).

## Constraints

**Do not bump the version. Do not tag. Do not touch `main`. Do not sign off the manual matrix.**
Do not reintroduce `uv sync --locked`. Do not remove `timid = true`.

## Deferred

The manual acceptance checklist (Task 10) is written but **unsigned** — it is a maintainer
release gate. The cross-platform job, once running, proves the app constructs and passes a test
subset on macOS and Windows; it does **not** prove native dialogs, clipboard, or drag/drop there.

STATUS: CHANGES_REQUESTED
