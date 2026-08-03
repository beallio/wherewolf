# Review — desktop-parity-2 (round 01)

Branch: `feat/desktop-parity-2` @ `976a333`
Reviewed against: `docs/plans/2026-08-02_desktop-parity-2.md`

## Verdict

APPROVED, with one process finding that the maintainer has waived.

All eight tasks landed and every feature is reachable from `MainWindow`. The second-tier
audit findings — code that worked but had no door — are closed.

## Process finding (waived by the maintainer)

The plan required one commit per task; the round delivered **one commit for all eight**.
That contradicts the atomic-commit policy in `CLAUDE.md` §10 and makes selective revert
impossible. The maintainer reviewed this and accepted it, so it does not block the merge.
Worth restating for future rounds rather than letting it become the norm.

## Reachability, measured by review

I did not read the session log. I constructed a real `MainWindow` offscreen and reached
each feature the way a user would:

```text
Edit menu   ['Undo','Redo','Cut','Copy','Paste','Select All','Find / Replace…','Toggle Comment']
Help menu   ['About','Documentation','Open-Source Licenses']
window title 'Wherewolf 0.5.2'
filter input preview_filter_input  (QLineEdit, placeholder "Filter preview rows")
run gating  empty catalog -> False;  after adding a dataset -> True
```

40 actions are now reachable, including the ones that were previously orphaned helpers:
`Export Selection…`, `Reveal in File Manager`, `Show Hidden Files`, `Preferences…`,
`Find / Replace…`, `Select All`, `Clear Preview Filter`.

## Spark availability — all four combinations

`_is_spark_available` now requires both `pyspark` and a `java` on PATH, and the failure
message names what is missing:

```text
pyspark=True  java=True  -> available=True
pyspark=True  java=False -> available=False  "Java is not available on PATH"
pyspark=False java=True  -> available=False  "pyspark is not installed; install wherewolf[spark]"
pyspark=False java=False -> available=False  both reasons, joined
```

The probe is `shutil.which("java")` — cheap, and it does not start a JVM on import, as
the plan required.

## Negative controls

The plan made these mandatory for tasks 1, 2, 6 and 7. All four bite:

| mutation | result |
|---|---|
| drop Find/Replace + Select All from the Edit menu | 1 failed, 40 passed |
| disconnect `preview_filter_input` from `set_filter_text` | 1 failed, 40 passed |
| force `run.setEnabled(True)` at both gates | 2 failed, 39 passed |
| `_is_spark_available` ignores Java | 1 failed, 18 passed |

Each fails a small, targeted number of tests and leaves the rest green.

**A note on my own first attempt**, since it matters for trusting this table: two of these
mutations initially failed to apply — one regex matched nothing and one produced no test
output at all. Both looked like passes. I re-ran them against the real call sites
(`main_window.py:554` for the filter wiring, `main_window.py:342` and `:765` for run
gating) before recording the results above. A mutation that does not apply is not
evidence of anything.

## Gates

```text
ruff check          All checks passed
ty check .          All checks passed   (whole repo, including tests/)
pytest              384 passed, 7 deselected   (was 370; +14 tests)
git status --short  clean
```

## The boundary held

Version still `0.5.2`. No tag, no `main` change. The `pyarrow` import survives,
`DontConfirmOverwrite` was not reintroduced, `timid = true` intact.

## Deferred

Native file-manager launching, real dialog appearance and call-tip rendering remain
manual maintainer checks, recorded in `docs/review/manual-acceptance-checklist.md`.
macOS and Windows are still covered only by the offscreen `qt-smoke` job.

STATUS: APPROVED
