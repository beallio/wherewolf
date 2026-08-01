# History v2 and persistent preferences — implementation session

Date: 2026-08-01

## Objective

Implement Phase 11 from `docs/plans/2026-08-01_history-v2-and-preferences.md`.

## Baseline

- Base commit: `6bb731a` (`docs(plans): scope phase 11 history v2 and persistent preferences`).
- Python 3.14: `307 passed, 1 skipped, 1 warning in 20.72s`.
- Python 3.12: `307 passed, 1 skipped, 1 warning in 14.38s`.
- Both baseline commands used `HOME=/tmp/wherewolf/home` so default history writes stay in the
  permitted temporary workspace. The initial unmodified 3.14 attempt without that isolated
  home failed with six test failures and one Qt teardown error because `/home/beallio/.wherewolf`
  is read-only in this sandbox; its output is retained at `/tmp/wherewolf/baseline-3.14.log`.

## Planned validation

- Run the plan's full quality gates and both-interpreter suite after implementation.
- Run the required mutation checks after committing the implementation.
- No human desktop verification, real-user-history migration, performance test, macOS test, or
  Windows test is planned for this Linux/offscreen session.
