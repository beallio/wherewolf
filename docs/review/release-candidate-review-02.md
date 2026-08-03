# Review — release-candidate (round 02)

Branch: `feat/release-candidate` @ `979e5a0`
Reviewed against: `docs/plans/2026-08-01_release-candidate.md` and review 01

## Verdict

APPROVED.

K1 is fixed, and CI now proves what no local check could: **the application builds, installs, and
runs on Linux, macOS and Windows.**

## K1 — fixed, and proven by a real run

`${{ runner.temp }}` at job scope is replaced with `${{ github.workspace }}`, which GitHub
accepts there, with a comment recording why:

```yaml
      # `runner` is unavailable at job scope. Keep these isolated from the
      # checked-out project while using a context GitHub accepts for this scope.
      UV_PROJECT_ENVIRONMENT: ${{ github.workspace }}/.wherewolf-qt-smoke-venv
```

The workflow previously failed to parse — zero jobs, zero seconds, no logs, no PR checks
scheduled. It now runs, which is the only evidence that counts for a server-side validation
error.

## V4 — the cross-platform criterion, satisfied for the first time

PR #11, all nine checks green:

```text
qt-smoke (ubuntu-latest)=SUCCESS   qt-smoke (macos-latest)=SUCCESS   qt-smoke (windows-latest)=SUCCESS
build=SUCCESS   lint=SUCCESS
test-duckdb (3.12)=SUCCESS   test-duckdb (3.14)=SUCCESS
test-spark (3.12)=SUCCESS    test-spark (3.14)=SUCCESS
```

**macOS and Windows have been listed as "unverified" in every deferred section since Phase 8.**
They are now genuinely exercised — and not by an import check: the job runs
`tests/test_qt_stack.py` and `tests/test_desktop_duckdb_flow.py`, so a real query executes
end-to-end through a real `MainWindow` on all three platforms. `fail-fast: false` means each
platform's result stands on its own.

That said, be precise about what it proves: the app **constructs and passes a widget/integration
subset offscreen**. Native dialogs, real clipboard behaviour and drag/drop on those platforms
remain manual.

## Final state — measured by review

| check | result |
|---|---|
| gates (3.14) | 354 passed, 7 deselected |
| CI, all legs | 9/9 SUCCESS across 3 OSes |
| license in **wheel** | `dist-info/licenses/LICENSE`, `LICENSES/MIT-pre-0.6.txt` |
| license in **sdist** | `LICENSE`, `LICENSES/MIT-pre-0.6.txt` |
| wheel metadata | `License-Expression: GPL-3.0-only` |
| clean-env install | fresh venv; `MainWindow` constructs offscreen |
| default install | no pyspark, no streamlit |
| per-leg audit test | mutation bites (both audit tests fail) |
| **V10** crash gate 25 + 25 | **0 native crashes / 50** |
| version | **0.5.2** — unchanged |
| tag | none |

## What this phase delivered

A build job that inspects the real artifacts, a clean-environment install smoke test, the
cross-platform Qt job, a per-leg install audit test that asserts properties rather than command
strings, a rewritten README, 0.5.x→0.6.0 migration notes, a changelog, and the manual acceptance
checklist.

Twelve commits across two rounds, one per task.

## The boundary held

No version bump, no tag, no `main` change, and the manual matrix left unsigned. Those were stated
as prohibitions rather than preferences, and they were respected exactly.

## What remains — for the maintainer only

**This is a release candidate, not a release.** Three things are yours:

1. **Execute the manual acceptance checklist** (`docs/review/manual-acceptance-checklist.md`).
   Nothing automated can cover native-dialog appearance, real clipboard integration,
   file-manager drag/drop, or UI responsiveness under a long query. The cross-platform CI job
   raises confidence on macOS and Windows but does not replace this.
2. **Bump to 0.6.0** when satisfied.
3. **Promote `dev` → `main` and release.**

One standing item worth a deliberate decision rather than inheritance: CI no longer runs
`uv sync --locked`, because a machine-global `exclude-newer = "7 days"` stamps a relative
`exclude-newer-span` into `uv.lock` that CI cannot reproduce. Lockfile verification is therefore
off. Restoring it means removing that relative constraint from lock generation — and any future
local `uv lock` would reintroduce it.

## Deferred and explicitly NOT verified

The manual matrix is unsigned. No performance measurement was taken — Section 22.6's targets
remain unmeasured. The cross-platform job does not prove native dialogs, clipboard or drag/drop
on macOS and Windows. Spark is verified on Linux with one JDK, `local[1]`, tiny data.

STATUS: APPROVED
