# Review — ci-qt-flake-312 (round 06)

Branch: `feat/ci-qt-flake-312` @ `5c72599`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

> **New implementer.** Previous rounds were run by a different agent. Everything you need is
> in this note plus the session log at
> `docs/agent_conversations/2026-07-31_ci-qt-flake-312.md`. Read both before starting.

## Where the investigation stands

**Established, do not re-measure:**

| fact | evidence |
|---|---|
| The crash is a native segfault (exit 139) at ~2%, right after `tests/test_actions.py` | multiple CI logs |
| It is **Python 3.12-specific** | probe `30683970309`: 3.12 → **4/10** segfaults, 3.14 → **0/10**, same commit and runner |
| Pooled 3.12 rate | **7 / 32 ≈ 22%** |
| Confirming a fix needs | **N ≈ 19** at sub-1% false-pass, i.e. 2 dispatches of the 3.12 arm |
| It has **never** reproduced locally | 0/20 on 3.12, 0/91 on 3.14, 0/6 pinned to 2 CPUs |
| A second, unrelated CI flake exists | `test_app_initialization` — Streamlit `AppTest` 3s timeout. **Do not fix**, just never conflate it with the segfault |

Local runs are a **useless predictor** here: local is 0/20 on 3.12 while CI measures ~22%.
Never validate a fix locally.

`a913e04`'s commit message blames coverage's C tracer under **Python 3.14** — the
interpreter that measures 0/10. That explanation is wrong and should be corrected in the
session log (not by rewriting the commit).

## Required changes

### B14. The directional probe modes are unreachable — encode the mode in a committed file

`5c72599` added `probe_mode` as a **`workflow_dispatch` input**. But `workflow_dispatch`
cannot be used here: GitHub only exposes it once the workflow exists on the repository's
**default branch** (`main`), and this workflow lives only on this feature branch. Dispatch
returns:

```text
HTTP 404: workflow flake-probe.yml not found on the default branch
```

The branch-scoped `push:` trigger is the **only** usable trigger, and on push `PROBE_MODE`
falls back to `baseline`. So the three modes you inherited can never actually run.

Make the mode a **committed file** the workflow reads. For example add `.github/probe-mode`
containing a single word, and in the probe step:

```yaml
- name: Resolve probe mode
  id: mode
  run: echo "value=$(tr -d '[:space:]' < .github/probe-mode)" >> "$GITHUB_OUTPUT"
```

Then branch on `steps.mode.outputs.value` for `baseline` / `no-cov` / `deselect` /
`timid-false`. Changing that file and pushing runs that mode. Keep the `workflow_dispatch`
input as a convenience if you like, but nothing may depend on it.

Keep the push trigger branch-scoped exactly as-is — it must remain incapable of firing on
`main` or `dev`:

```yaml
push:
  branches:
    - feat/ci-qt-flake-312
```

### B15. Push, and verify the probe actually ran, before marking the round complete

The last three rounds each edited the workflow, marked the round complete, and **never
dispatched a probe** — the branch was left unpushed and no run existed. The edits were made;
that they took effect was never checked.

Every measurement round must end with:

```bash
git push origin feat/ci-qt-flake-312
gh run list --workflow flake-probe.yml --limit 1 \
  --json databaseId,headSha,status --jq '.[0]|"\(.databaseId) \(.status) sha=\(.headSha[0:7])"'
```

**If no run exists at your HEAD sha, the round is not complete.** Wait for it to finish and
record the result.

### B16. Run the three narrowing dispatches, 3.12 arm only

Restrict the matrix to `python-version: ["3.12"]` while narrowing — 3.14 is measured clean
and testing it again wastes half the jobs.

One mode per dispatch, each compared against the 22% baseline:

1. **`no-cov`** — `--no-cov` on the pytest step. Highest value: if 3.12 goes clean without
   coverage, the interaction is confirmed coverage-related *and* version-specific.
2. **`deselect`** — deselect `tests/test_actions.py`, `tests/test_main_window.py`,
   `tests/test_catalog_dock.py`, `tests/test_sql_editor.py`. Does the crash follow the
   widget tests?
3. **`timid-false`** — override `timid = false` for the probe only (do **not** commit that
   change to `pyproject.toml`). Quantifies what `timid` actually buys on the interpreter
   that crashes; its benefit was only ever measured on 3.14.

Count with the three-way classifier already in the session log — crash / ordinary / unknown,
with the accounting cross-check. A missing or unreadable log is `unknown`, never
"not a crash".

Each dispatch is 10 samples, which **cannot** distinguish 22% from 8%. Report each as
**directional** evidence and say so explicitly.

### B17. Stop and report

Do **not** attempt a fix in this round. Report the three rates and stop. A mitigation option
is on the table that may make deep fix work unnecessary, and that decision needs this data.

Also fix the stale `2 / 10` figure if it still appears anywhere in the session log; only the
corrected `1 / 10` for probe run 2 should survive.

## Constraints

Do not remove `timid = true` from committed config. Do not disable coverage in `ci.yml`. Do
not skip, delete or xfail tests. Do not drop either leg from `ci.yml`. Do not touch `main`.
Probe triggers must never be able to fire on `main` or `dev`.

## Not verified

- **No candidate fix has been tested.**
- **No narrowing data exists yet** — that is this round's entire purpose.
- The 3.14 result is 10 samples: strongly suggestive of a much lower rate, not proof of
  zero. At a true 5% rate, 0/10 occurs 60% of the time.

STATUS: CHANGES_REQUESTED
