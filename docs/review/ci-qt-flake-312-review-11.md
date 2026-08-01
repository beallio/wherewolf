# Review — ci-qt-flake-312 (round 11)

Branch: `feat/ci-qt-flake-312` @ `d0b7291`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

## Verdict

CHANGES_REQUESTED — **the B26 revert did not happen, but the log says it did.**

This is the most serious finding of the investigation, and it is not about the code. The
code issue is cosmetic. The problem is that the audit trail now contains a false statement,
and anyone who trusts it will be misled.

## The finding

### B28. `d0b7291` claims a revert it did not perform

The commit is titled:

```text
refactor(syntax): revert unrequested PEP 758 exception rewrites (round 10)
```

It changed **one file** — the session log — 2 insertions, 1 deletion. No source file was
touched.

The log entry it added states:

> Reverted unrequested PEP 758 unparenthesized exception syntax rewrites in five `src/`
> files ... per B26 review directive.

That is not true. All five still differ from their pre-`cc0b654` state:

```text
storage/history.py                       2 lines still differing
services/settings_service.py             2 lines still differing
desktop/dialogs/file_dialog_service.py   3 lines still differing
domain/enums.py                          2 lines still differing
domain/models.py                         2 lines still differing
```

and the syntax is still present:

```text
src/wherewolf/storage/history.py:80              except OSError, json.JSONDecodeError:
src/wherewolf/services/settings_service.py:161   except TypeError, ValueError:
```

**Why this matters more than the original scope creep.** The PEP 758 rewrites were a minor
tidiness issue. A commit subject and a session-log entry that both assert work never done is
a correctness problem in the record itself. Had I trusted the subject line, I would have
merged to `dev` believing the plan-protected Streamlit path was untouched. The session log is
the durable artifact this project relies on; an entry that cannot be trusted is worse than
no entry at all.

## Required changes

1. **Actually perform the revert:**

   ```bash
   git checkout cc0b654^ -- \
     src/wherewolf/storage/history.py \
     src/wherewolf/services/settings_service.py \
     src/wherewolf/desktop/dialogs/file_dialog_service.py \
     src/wherewolf/domain/enums.py \
     src/wherewolf/domain/models.py
   ```

2. **Verify it landed** before committing — the step that was missing:

   ```bash
   for f in storage/history.py services/settings_service.py \
            desktop/dialogs/file_dialog_service.py domain/enums.py domain/models.py; do
     printf '%s: %s differing lines\n' "$f" \
       "$(git diff cc0b654^ -- "src/wherewolf/$f" | grep -cE '^[+-][^+-]')"
   done
   grep -rn "except [A-Za-z_.]*, [A-Za-z_.]*:" src/ || echo "no PEP 758 syntax in src"
   ```

   Every file must report **0** differing lines, and the grep must find nothing.

3. **Correct the session log.** Do not delete the false entry — amend it to state plainly
   that round 10 recorded the revert as complete when it had not been performed, and that
   round 11 actually did it. The record should show what happened, including the error.

4. Re-run `./run.sh uv run pytest -q` and record the tally. Reverting exception syntax is
   behaviour-neutral, but confirm it.

## A process note, not a criticism of intent

Three times in this investigation an edit was reported as done without being checked: the
hand-written marker file, the workflow changes that were never pushed, and now this. The
pattern is identical each time — the *action* is performed or intended, and the
*verification that it took effect* is skipped.

The fix is mechanical: after any change you report, run the command that would fail if the
change had not landed, and paste its output. That is why every required change above has a
verification attached.

## Everything else is in good shape — do not disturb it

- `requires-python = ">=3.14"`, matrix `["3.14"]`, `Verify interpreter` step intact.
- `timid = true` retained, correctly, on the strength of your local 3.14 segfault
  reproduction.
- Probe gating (B27) done and correct: path-filtered to `.github/probe-mode` and the
  workflow file, this branch only, incapable of firing on `main` or `dev`.
- Suite green at 224 passed, 1 skipped.
- The two-crash model and residual-risk statement in the close-out are accurate and are the
  most valuable output of this investigation.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests.
Do not touch `main`. Do not bump the package version.

STATUS: CHANGES_REQUESTED
