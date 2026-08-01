# Session Log: 2026-07-31 - Fix Qt Coverage Flake

- **date**: 2026-07-31
- **task objective**: Investigate and fix intermittent Qt native crashes (`Fatal Python error: Aborted` / `Segmentation fault`) occurring during `pytest` runs under coverage.
- **files modified**:
  - `docs/plans/2026-07-31_qt-coverage-flake.md`
  - `docs/agent_conversations/2026-07-31_qt-coverage-flake.md`
- **tests added**: None (baseline measurement phase)
- **design decisions**:
  - Follow plan-mandated empirical hypothesis testing with explicit sample sizes.
- **results**:
  - Measured baseline with coverage ON (`/tmp/wherewolf/flake.sh 30`): `crashes: 2 / 30` (crashes on run 4, run 6)
  - Measured baseline with coverage OFF (`/tmp/wherewolf/flake.sh 30 --no-cov`): `crashes: 0 / 30`
