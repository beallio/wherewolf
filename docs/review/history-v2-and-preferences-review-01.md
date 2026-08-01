# Review — history-v2-and-preferences (round 01)

Branch: `feat/history-v2-and-preferences` @ `e1891de`
Reviewed against: `docs/plans/2026-08-01_history-v2-and-preferences.md`

## Verdict

CHANGES_REQUESTED — **one required change, and it is a test-isolation defect you already
worked around rather than fixed.** The implementation itself is correct and I found no
functional defects.

## What you did well

- **Fourteen atomic commits in plan order**, with the entire storage layer landing Qt-free
  before the dock existed.
- **The storage tests map 1:1 to the plan's requirements** — versioned ids, migration in order
  and only once, existing-v2 untouched, failed migration leaving the original intact, malformed
  isolation, unparseable file not deleted, missing-key skipped, `get_by_id`, cap evicting
  oldest, and a **parametrized** Streamlit-shape test covering both migrated and fresh files.
  That last one is the compatibility guarantee and you tested both paths, which is what the
  plan asked for and easy to half-do.
- **Migration is tested at realistic scale** — 100 records, order preserved, idempotency
  asserted. A single-record test would have proven nothing about ordering or the cap.
- **The dock selects by stable id**, carrying `record["id"]` in `Qt.ItemDataRole.UserRole` and
  resolving through `get_by_id`. This is the exit criterion and the design is right.
- **`app.py` is untouched** and the Streamlit path diff is empty. The compatibility constraint
  held.
- **The session log is the best this project has produced.** Both baselines, both final
  tallies, mutation node ids, and — importantly — *"`closeEvent` was not changed, so V10 was
  not applicable"* rather than claiming an unmeasured result. **I verified that claim and it is
  accurate**: `closeEvent` appears in the diff only as unchanged context. That is exactly the
  recording discipline the plan asked for.

### My measurements

| check | result |
|---|---|
| suite on **3.14** | 333 passed, 1 skipped |
| suite on **3.12** | 333 passed, 1 skipped — identical |
| `run-quality-gates` | pass |
| **V10** crash gate 25 + 25 | **0 native crashes / 50** |
| **V9** 3.14-only syntax | none |
| V2 Streamlit path diff | empty |
| V8 mutation 1 (select by list index) | FAILED `test_history_dock_selects_duplicate_labels_by_stable_id` |
| V8 mutation 3 (malformed discards all) | FAILED `test_malformed_records_are_isolated_from_valid_history`, `test_record_missing_required_key_is_skipped` |

I ran V10 despite it being "not applicable" — a new dock is new QObject lifetime, and the
result is clean at 0/50. You do not need to re-run it.

## Required change

### F1. 37 tests now read the user's real history file

`HistoryDock.__init__` ends with `self.refresh()`, which reads from disk, and `MainWindow`
constructs the dock unconditionally with `history_manager or HistoryManager()` —
whose `DEFAULT_PATH` is `~/.wherewolf/history.json`.

**37 tests construct `MainWindow` without injecting a history manager.** Every one of them now
reads the developer's real history file. This is **new in this phase**: I checked `dev`, which
had zero reads at construction.

You already hit this. Your own session log records it:

> The initial unmodified 3.14 attempt without that isolated home failed with **six test
> failures and one Qt teardown error** because `/home/beallio/.wherewolf` is read-only in this
> sandbox.

You solved it by pointing `HOME` at a writable temporary directory. That got the round done,
but it treated the symptom: the suite's correctness now depends on ambient user state. It
passes on this machine because my `~/.wherewolf/history.json` happens to be small and
well-formed. On a machine whose history is large, or contains one of the malformed records
this very phase teaches the reader to expect, tests that never intended to touch it would fail
in ways that look like real regressions.

**This matters more now, not less.** `ORCH_ADD_DIRS` has since been granted
`~/.wherewolf` and `~/.config/Wherewolf` so the sandbox no longer blocks writes. The sandbox
was accidentally acting as a safety net. A future test that triggers a destructive path on a
default-constructed `MainWindow` can now write to the real file. Your Clear History test
correctly injects a `tmp_path` manager — keep that discipline, but do not rely on every future
test remembering.

**Fix:** an autouse fixture in `tests/conftest.py` that redirects the history default path (and
`QSettings` storage, which has the same exposure through `SettingsService`) to a per-test
temporary location. Then assert it: a test proving that constructing a bare `MainWindow()` does
**not** touch `~/.wherewolf`. Given this phase's entire purpose is not mishandling user history,
that guarantee belongs in the suite.

## Already handled — no action needed

`.codex/config.toml`, a machine-specific codex MCP config, was left untracked in the repo root
and was breaking the `git status --short` must-print-nothing check that every round's
verification depends on. I added `.codex/` to `.gitignore` myself (`cef3342`) since it is
tooling hygiene rather than phase work. The tree is clean.

## Verification before marking complete

- The autouse isolation fixture, plus the test proving a bare `MainWindow()` does not touch
  `~/.wherewolf`.
- `./run.sh uv run pytest -q` on 3.14 and `--python 3.12` — record both.
  **Remember:** `uv run --python 3.12` re-syncs the shared venv; restore with
  `./run.sh uv sync --all-extras --dev --python 3.14`.
- `scripts/orchestration/run-quality-gates` → exit 0.
- `git status --short` → prints nothing.

**Do not re-run V10** (0/50 measured above) or the V8 mutations unless you change source.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests. Do
not modify `app.py` or the Streamlit path beyond `storage/history.py`. Do not regress the
atomic write. Do not touch `main`. Do not bump the package version.

## Deferred — correctly recorded by you

No human has seen the dock or a restored layout; all Qt tests are offscreen. No migration has
been run against a real user's history file. No performance measurement. macOS and Windows
unverified — `QSettings` backends differ per platform and this is Linux-only verification.
Export is Phase 12, Spark Phase 13, Streamlit removal Phase 14.

STATUS: CHANGES_REQUESTED
