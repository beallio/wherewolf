# Review 01 — query-workspaces

**Branch:** `feat/query-workspaces`
**Head reviewed:** `40a5b84`
**Base:** `dev` (`85c1fb2`)
**Gates as re-run by the reviewer:** `603 passed, 7 deselected`, coverage 90%. Baseline on
`dev` was `584 passed`, so this round adds 19 tests. `run-quality-gates` passes, tree
clean, no review notes deleted. The real `~/.wherewolf/` was checksummed before the round
and after a full suite run: unchanged.

## Summary

This is the strongest round of the three. Nine tasks, ten atomic commits, and every
high-risk item in the plan handled correctly — including the two silent-failure modes
(`::` cast mis-parsing and string-interpolated binding) that the plan was rewritten
around. One minor gap blocks: a defensive branch that the plan explicitly required be
either tested or recorded, and which is currently neither.

Reviewer-verified mutation results (re-measured, not read from the session log):

| Mutation | Result |
|---|---|
| render regardless of originating tab | `1 failed, 114 passed` |
| drop `_result_origin_by_request_id` tracking | `1 failed, 114 passed` |
| naive `:name` regex extraction | `2 failed, 1 passed` |
| naive `str.replace` binding | `1 failed, 3 passed` |
| `SavedQueryStore.load` raises on malformed JSON | `1 failed, 4 passed` |
| `{dataset}` substituted without `quote_identifier` | `1 failed, 115 passed` |
| `tabCloseRequested` disconnected | `1 failed, 114 passed` |
| **Spark bound-parameter refusal removed** | **`8 passed` — no test detects this** |

---

## MECHANICAL — must fix

### M1. Spark's bound-parameter refusal is untested and unrecorded

`src/wherewolf/execution/spark_engine.py:132-137`

The implementation is **correct**. Reviewer-verified directly:

```text
success: False
error  : Spark does not support bound query parameters
```

The problem is that nothing protects it. Plan task B3 said:

> Do the same for the Spark adapter or explicitly raise there and record the limitation
> in the session log — do not silently fall back to string substitution on one engine
> while binding on the other.

You correctly chose the "explicitly raise" branch, but neither half of the obligation
that came with it was met:

1. **No test.** `grep -rn "does not support bound\|bound query parameters" tests/` returns
   nothing, and removing the `if params:` guard leaves `tests/test_spark_engine.py` fully
   green at `8 passed`. This is the only branch in the round with no negative control.
2. **Not in the session log.** `deferred_and_unverified` in
   `docs/agent_conversations/2026-08-17_query-workspaces.json` lists four items — tab
   performance, string-only parameters, lexer dialect coverage, and monkeypatched
   dialogs — none of which mention that parameterised saved queries do not work on Spark
   at all.

This matters beyond bookkeeping. Today a Spark user who runs a parameterised saved query
gets a clear, actionable message. If that guard regressed, they would instead get an
opaque Spark parse error about an unbound `?`, and nothing in the suite would notice. The
guard's value *is* the good error message, so the good error message is what needs
pinning.

**Fix, two parts:**

Add to `tests/test_spark_engine.py`:

```python
def test_spark_engine_refuses_bound_parameters() -> None:
    engine = SparkEngine.__new__(SparkEngine)
    result = SparkEngine.execute(engine, "SELECT ?", params=["x"])

    assert result.success is False
    assert result.error_message == "Spark does not support bound query parameters"
```

Note this must not require PySpark — the guard returns before the `SPARK_AVAILABLE`
check, which is why constructing via `__new__` works and why the test runs in the default
tier.

Then add to `deferred_and_unverified` in the session log:

```text
Parameterised saved queries are DuckDB-only. SparkEngine.execute rejects bound
parameters with an explicit error rather than interpolating them; Spark users cannot run
saved queries that declare :parameters.
```

---

## Confirmed good

Verified by direct execution, not by reading tests:

- **`extract_parameters` is genuinely lexer-aware.** All seven adversarial cases pass:
  `a::int` yields no parameters, `':notaparam'` and `":alsonot"` yield none, `-- :nope`
  and `/* :nope */` yield none, repeated `:x` de-duplicates in first-appearance order, and
  `SELECT a::int ... WHERE b = :real` correctly yields exactly `("real",)`. This was the
  single most likely silent failure in the plan and it is right.
- **`bind_parameters` transports values as data.** `'; DROP TABLE t; --` produces
  `WHERE name = ?` with the payload in the values list; `DROP` never reaches the SQL
  string. On the tricky input it preserves the string literal, the `::` cast, and the
  trailing comment while rewriting only the real placeholder — i.e. it is reusing the
  scanner's spans rather than re-scanning with a looser rule, exactly as required.
- **`execute()` was genuinely extended** (`duckdb_engine.py:62-69`) with
  `params: list[object] | None = None` defaulting to `None`, so existing callers are
  unaffected. No string interpolation anywhere.
- **A1 is a real pure refactor.** `git diff --name-only d7acb7b~1 d7acb7b` returns only
  `src/wherewolf/desktop/main_window.py` — no test file was touched to keep it green.
- **Per-tab file state was migrated, not left window-global.** `_EditorTabState`
  (`:107-113`) owns `path`, `last_saved_text`, `last_request`, and `last_result`, and
  `_current_sql_path` is now a property over the current tab's state (`:368-373`). Save
  cannot write one tab's buffer to another tab's file.
- **`tabCloseRequested` is connected** (`:1423`), not merely `setTabsClosable(True)`
  (`:1303`).
- **`{dataset}` is quoted** via `quote_identifier` (`:715`).
- Storage mirrors `HistoryManager`, and `tests/test_saved_query_store.py` covers round
  trip, corrupt file, malformed-entry skipping, and interrupted write.

---

## Required before the next round

1. Add the Spark refusal test and confirm removing the `if params:` guard turns
   `tests/test_spark_engine.py` red; record that red output.
2. Add the Spark limitation to `deferred_and_unverified` in the session log.
3. Re-run `scripts/orchestration/run-quality-gates` and record the tallies.

STATUS: CHANGES_REQUESTED
