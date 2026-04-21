# Plan: Code Review Fixes Implementation

## Problem Definition
The code review identified several critical and medium-priority issues:
1. SQL Injection vulnerability in `DuckDBEngine`.
2. Non-functional query cancellation in the Streamlit UI.
3. Performance bottleneck in `SparkEngine` due to redundant actions.
4. Data loss risk in `HistoryManager` due to non-atomic writes.
5. Inconsistent translation panel state in the UI.

## Architecture Overview
- **Infrastructure:** Update `HistoryManager` to use atomic filesystem operations.
- **Core Logic:** Parametrize SQL in `DuckDBEngine` and optimize `SparkEngine` preview logic.
- **UI:** Integrate `ThreadPoolExecutor` for background execution and fix state tracking for translations.

## Dependency Requirements
- `concurrent.futures.ThreadPoolExecutor` (stdlib)
- `tempfile` (stdlib)
- `pathlib` (stdlib)

## Git Strategy
- Branch: `feat/code-review-fixes`
- Commit Frequency: Atomic commit per task.
- Protocol: `run.sh uv run pytest` and `run.sh ruff` before each commit.

## Phased Approach

### Phase 1: DuckDB SQL Injection Fix
- **Task 1.1:** Create `tests/test_duckdb_sql_injection.py` reproducing the issue.
- **Task 1.2:** Implement parametrized query in `src/wherewolf/execution/duckdb_engine.py`.
- **Task 1.3:** Verify with tests.

### Phase 2: History Atomic Writes
- **Task 2.1:** Create `tests/test_history_atomicity.py`.
- **Task 2.2:** Update `src/wherewolf/storage/history.py` to use `tempfile` and `os.replace`.
- **Task 2.3:** Verify with tests.

### Phase 3: Spark Engine Optimization
- **Task 3.1:** Create `tests/test_spark_engine_optimization.py`.
- **Task 3.2:** Optimize `src/wherewolf/execution/spark_engine.py`.
- **Task 3.3:** Verify with tests and benchmark.

### Phase 4: UI Cancellation
- **Task 4.1:** Create `tests/test_app_cancel.py` (using mocks).
- **Task 4.2:** Refactor `src/wherewolf/app.py` to use `ThreadPoolExecutor`.
- **Task 4.3:** Verify with tests.

### Phase 5: UI Translation State
- **Task 5.1:** Create `tests/test_app_translation_state.py`.
- **Task 5.2:** Update `src/wherewolf/app.py` to track executed query state.
- **Task 5.3:** Verify with tests.

### Phase 6: Final Validation
- **Task 6.1:** Run full test suite.
- **Task 6.2:** Run Principal Engineer Code Review.
