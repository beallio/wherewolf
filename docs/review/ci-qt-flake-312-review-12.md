# Review — ci-qt-flake-312 (round 12)

Branch: `feat/ci-qt-flake-312` @ `c92fbda`
Reviewed against: `docs/plans/2026-07-31_ci-qt-flake-312.md`

## Verdict

**Reviewer error. B26 and B28 are withdrawn in full.** No further changes are required for
them. The implementation is correct as it stands.

## Withdrawal of B26 (round 10) and B28 (round 11)

I asked for the PEP 758 exception-syntax rewrites in five `src/` files to be reverted as
unrequested scope creep. When two consecutive rounds produced no `src/` diff, I escalated in
round 11 and stated that the session log "contains a false statement", calling it "the most
serious finding of the investigation".

**That accusation was wrong, and the underlying finding was wrong.** I have now reproduced
the mechanism directly:

```text
$ git checkout cc0b654^ -- src/wherewolf/storage/history.py
80:        except (OSError, json.JSONDecodeError):      <- reverted, parenthesized

$ ruff check src/wherewolf/storage/history.py --fix
All checks passed!                                      <- linter leaves it alone
80:        except (OSError, json.JSONDecodeError):

$ ruff format src/wherewolf/storage/history.py
1 file reformatted
80:        except OSError, json.JSONDecodeError:        <- FORMATTER re-applies PEP 758
```

`ruff format` drops the now-redundant parentheses because `requires-python = ">=3.14"` makes
it target Python 3.14, where PEP 758 permits unparenthesized multiple exception types. The
pre-commit hook runs `ruff format .` on every commit.

So the sequence in rounds 10 and 11 was:

1. the revert was performed, exactly as instructed;
2. the pre-commit hook ran `ruff format .` and immediately re-applied the syntax;
3. the net `src/` diff was zero, so only the session log appeared in the commit.

**The revert was mechanically impossible to land while the 3.14 floor and the hook both
exist.** The session log was accurate. The implementer did what was asked, twice, and my
escalation was unjust.

I also reverted three further files (`file_dialog_service.py`, `enums.py`, `models.py`) on
the same mistaken basis. Those changes were `UP035`/`UP037` fixes that ruff **requires**
under the 3.14 target — reverting them produced 3 lint errors. Also my error.

### Correct position

All five files' changes are legitimate and must stay. They are a mechanical consequence of
raising `requires-python` to `>=3.14`, produced by the project's own formatter and linter,
not a stylistic choice by the implementer. The fact that one of them lives in the
plan-protected Streamlit path (`storage/history.py`) is unavoidable: the toolchain reformats
the whole repository, and the plan's protection cannot survive a floor bump. That is worth
noting in the close-out, but it is not a defect.

### What I should have done

When two rounds reported a revert with no resulting diff, my first move should have been to
reproduce the revert myself and observe what happened to it — which took three commands and
immediately showed the formatter re-applying the change. Instead I inferred bad reporting
from absent evidence. That is precisely the failure I had just described to the implementer
in round 11: performing an action and skipping the check that it took effect.

## Required change

### B29. Record this correction in the session log

Append a short, factual entry:

- rounds 10 and 11 asked for a revert of PEP 758 exception syntax in five `src/` files;
- the revert could not persist, because `ruff format` re-applies it under
  `requires-python = ">=3.14"` (PEP 758) and the pre-commit hook runs the formatter;
- the reviewer withdrew B26 and B28 in round 12 and confirmed the mechanism by reproduction;
- the five files' changes are correct and intentional consequences of the 3.14 floor;
- note that raising the floor caused a repository-wide reformat that necessarily touches the
  Streamlit path the plan protects, and that this is expected rather than scope creep.

Do not delete the earlier entries. The record should show the sequence, including my error.

## Everything else is complete and correct

- `requires-python = ">=3.14"`, matrix `["3.14"]`, `Verify interpreter` step intact.
- `timid = true` retained on the strength of your local 3.14 segfault reproduction — the
  best single piece of evidence produced in this investigation.
- Probe workflow gated to `.github/probe-mode` and the workflow file, this branch only;
  cannot fire on `main` or `dev`.
- Gates green: `ruff check` clean, `ruff format --check` clean (112 files),
  `ty check src/` clean, **224 passed, 1 skipped**.
- Close-out documents the two-crash model, the unexplained 3.12 root cause, the residual
  risk at 0/30, and the separate `AppTest` flake.

After B29, this branch is ready to merge.

## Constraints

Do not remove `timid = true`. Do not revert the PEP 758 or `UP` changes. Do not disable
coverage. Do not touch `main`. Do not bump the package version.

STATUS: CHANGES_REQUESTED
