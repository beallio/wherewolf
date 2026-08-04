# Review — desktop-shell-ui-fixes (round 02)

Branch: `feat/desktop-shell-ui-fixes`
Reviewed against: `docs/plans/2026-08-03_desktop-shell-ui-fixes.md`
Reviewed at: `f81286b3439e9749622e30e08bc47ecbf693f479`
Prior round: `docs/review/desktop-shell-ui-fixes-review-01.md`

## Verdict

Both round-01 findings are resolved, and resolved properly rather than papered
over. One new finding, introduced by the fix for finding 1 — and partly caused by
imprecise wording in my own review note, which I own below.

## Round-01 findings — verified fixed

**Finding 1 (ty gate).** Verified independently, with no `--config` flag:

- `/tmp/wherewolf/ty-baseline.toml` — deleted, confirmed absent.
- `./run.sh uv run ty check src/` → `All checks passed!`, exit 0.
- `./run.sh uv run ty check .` → `All checks passed!`, exit 0.

The stale `# ty: ignore[unresolved-attribute]` suppressions were removed from
`src/wherewolf/execution/spark_engine.py:35` and `tests/conftest.py:27` rather
than re-suppressed, and the `tests/test_main_window.py` type error was fixed by
making the fake a real `SchemaWorker` subclass instead of by an ignore comment.
That is the right shape of fix.

**Finding 2 (cancellation message).** Fixed via a tracked `self._query_status`
and a branch in `_update_elapsed_status` that renders `Cancelling... (Ns)`
(`main_window.py:468-474`). The new test
`test_main_window_elapsed_timer_preserves_cancellation_status` asserts both the
positive (`"cancell" in message`) and the negative (`"Executing query..." not in
message`), which is what makes it bite.

## Gate status

Independently re-run by the reviewer:

- `./run.sh uv run pytest` → **447 passed, 7 deselected**, exit 0.
- `./run.sh uv run ty check src/` → exit 0.
- `./run.sh uv run ty check .` → exit 0.
- `scripts/check_cache_budget.sh` → exit 0, `cache bytes: 2134763082` (50% of
  the 4 GiB budget).

## Required changes

### Finding 3 (blocking) — the ty import check is now disabled repo-wide

`pyproject.toml` gained:

```toml
[tool.ty.rules]
unresolved-import = "ignore"
```

This is global. It does not scope the suppression to pyspark, to the optional
extra, or to a file — it turns off unresolved-import detection for the entire
project.

Demonstrated, not theorised. I dropped this file into `src/`:

```python
# src/wherewolf/_ty_probe.py
from definitely_not_a_real_module import something
```

and `./run.sh uv run ty check src/` reported `All checks passed!` with exit 0.
A completely bogus import in shipped source is now invisible to the gate. (The
probe file was removed immediately; `git status src/` is clean.)

That matters more than usual here because `src/wherewolf/execution/spark_engine.py:32`
resolves `pyspark.sql` dynamically through `import_module`, and the execution
registry selects engines at runtime — import mistakes in that area are exactly
what a static import check is for.

**My share of this:** review-01 told you to "prefer a committed `[tool.ty]`
setting in `pyproject.toml` over a source edit". You did precisely that. The
instruction failed to say *scoped to the offending import*, and this finding is
the consequence. Correcting it now, not holding it against the round.

The suppression only ever needed to cover one line. The sole real pyspark import
statement in the tree is:

```
tests/conftest.py:27:        from pyspark.sql import SparkSession
```

`spark_engine.py` reaches pyspark through `import_module("pyspark.sql")`, a
string argument ty does not resolve as an import, so it needs nothing.

Required:

- remove `[tool.ty.rules] unresolved-import = "ignore"` from `pyproject.toml`;
- suppress the single genuine site instead. Narrowest first: a
  `# ty: ignore[unresolved-import]` on `tests/conftest.py:27` with a short comment
  saying it is unresolvable without the optional `spark` extra. If ty in this
  version supports a path-scoped override block, that is equally acceptable —
  determine which mechanism this ty version actually honours rather than assuming,
  and record what you found;
- prove the narrowed configuration still catches real breakage. Recreate the
  probe above, confirm ty **fails** on it, record the exact diagnostic, then
  delete the probe and confirm `git status` is clean. A configuration that
  silences pyspark but also silences the probe has not fixed this finding;
- re-run `./run.sh uv run ty check src/` and `./run.sh uv run ty check .` and
  record both exit statuses.

## Non-blocking observations

1. `NeverFinishesWorker` (`tests/test_main_window.py:1299`) overrides
   `__getattribute__` to swap in `_fake_wait`. It works and it type-checks, but
   `__getattribute__` intercepts *every* attribute access on a live `QThread`
   subclass, which is a lot of surface for a test double. If a plain
   `def wait(self, *args: object) -> bool:` override satisfies ty, prefer it. Not
   worth a round on its own — fold it in only if you are already touching the file
   for finding 3.
2. Carried forward unaddressed from review-01, still non-blocking: the shutdown
   timeout message goes to a status bar on a closing window; `add_paths` surfaces
   warnings twice; `ExportController.shutdown` assigns rather than ANDs its
   result.

## Confirmed sound

- no review notes deleted; review-01 is committed as an audit record;
- working tree clean apart from the user's pre-existing untracked
  `feature-ideation-workbench-depth.md`;
- test count moved 446 → 447, consistent with exactly one added test;
- cache budget still comfortably under ceiling and the symlink is intact.

STATUS: CHANGES_REQUESTED
