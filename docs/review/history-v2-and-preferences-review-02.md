# Review — history-v2-and-preferences (round 02)

Branch: `feat/history-v2-and-preferences` @ `e960e07`
Reviewed against: `docs/plans/2026-08-01_history-v2-and-preferences.md` and review 01

## Verdict

APPROVED.

F1 is fixed, and fixed more completely than I asked for.

## F1 — resolved, and verified load-bearing

The autouse fixture in `tests/conftest.py` redirects `HistoryManager.DEFAULT_PATH` to a
per-test temporary location. **It also redirects `QSettings`** — both `IniFormat` and
`NativeFormat` at `UserScope` — which I flagged as having the same exposure but did not
require. Covering it unprompted is the right call: `SettingsService` writes to
`~/.config/Wherewolf`, and this phase adds settings round-trip and corrupt-value tests.

The assertion test is genuine, not decorative:

```python
def test_bare_main_window_does_not_touch_user_history(...):
    monkeypatch.setattr(HistoryManager, "_ensure_storage", assert_isolated_storage)
    assert window.history_manager.storage_path != user_history_path
    assert Path(window._settings_service._settings.fileName()).is_relative_to(tmp_path)
```

It hooks `_ensure_storage` so the check fires on the real construction path rather than
inspecting an attribute after the fact, and it asserts both the history path **and** the
settings file location.

I confirmed the fixture is load-bearing by removing the `DEFAULT_PATH` redirect:

```text
FAILED tests/test_main_window.py::test_bare_main_window_does_not_touch_user_history
```

So the guarantee is enforced, not merely asserted alongside an already-safe default.

## Final state — measured by review

| check | result |
|---|---|
| suite on **3.14** | 334 passed, 1 skipped |
| suite on **3.12** | 334 passed, 1 skipped — identical |
| `run-quality-gates` | pass |
| **V10** crash gate 25 + 25 (round 01) | 0 native crashes / 50 |
| **V9** 3.14-only syntax | none |
| **V2** Streamlit path diff | empty; `app.py` untouched |
| V8 mutation 1 (index selection) | bites |
| V8 mutation 3 (malformed discards all) | bites |
| isolation fixture removed | test FAILS, as it must |
| `git status --short` | clean |

## What this phase delivered

Schema-v2 history records with UUIDs, on-read v1 migration that preserves order and is
idempotent, per-record malformed isolation, id-based lookup, a History dock that selects by
stable id, SQL and catalog restore with missing files reported, corrupt-settings fallback,
window/dock/splitter restore, and Reset Layout plus Clear History.

Three things deserve specific credit:

- **The migration is tested at realistic scale** — 100 records, order preserved, run twice to
  prove idempotency. A single-record test would have proven nothing about ordering or the cap.
- **Malformed-record isolation replaces a silent total-loss path.** The previous
  `except (OSError, json.JSONDecodeError): return []` discarded a user's entire history on one
  corrupt byte. That is the worst failure mode this phase could have had, and it is now
  covered by tests asserting surviving count *and* contents.
- **The dock cannot reproduce the `app.py` defect.** Selection resolves through
  `get_by_id`, and the duplicate-label test fails immediately if selection becomes
  index-based — I verified that by mutation.

The Streamlit compatibility guarantee held: `app.py` is unmodified and every record still
exposes `timestamp` and `query` in the v1 read shape, tested for both migrated and fresh files.

## Note on the sandbox interaction

Round 01 surfaced this defect as six test failures in codex's sandbox, because
`~/.wherewolf` was read-only there. `ORCH_ADD_DIRS` has since been granted `~/.wherewolf` and
`~/.config/Wherewolf`, so that sandbox no longer blocks writes — it had been acting as an
accidental safety net. Fixing the isolation properly, rather than relying on the sandbox, is
what makes that grant safe.

## Deferred and correctly recorded

No human has seen the dock or a restored layout; all Qt tests are offscreen. **No migration has
been run against a real user's history file.** No performance measurement. macOS and Windows
unverified — `QSettings` backends differ per platform and this is Linux-only verification.
Export is Phase 12, Spark Phase 13, Streamlit removal Phase 14.

STATUS: APPROVED
