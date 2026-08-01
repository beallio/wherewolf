# Session Log: 2026-07-31 - Fix Qt Coverage Flake

- **date**: 2026-07-31
- **task objective**: Investigate and fix intermittent Qt native crashes (`Fatal Python error: Aborted` / `Segmentation fault`) occurring during `pytest` runs under coverage.
- **files modified**:
  - `docs/plans/2026-07-31_qt-coverage-flake.md`
  - `docs/agent_conversations/2026-07-31_qt-coverage-flake.md`
- **tests added**: None
- **design decisions**:
  - Follow plan-mandated empirical hypothesis testing with explicit sample sizes.
- **results**:
  - Measured baseline with coverage ON (`/tmp/wherewolf/flake.sh 30`): `crashes: 2 / 30` (crashes on run 4, run 6)
  - Measured baseline with coverage OFF (`/tmp/wherewolf/flake.sh 30 --no-cov`): `crashes: 0 / 30`
  - Task 2: `concurrency = ["thread"]` in `pyproject.toml` resulted in `3 / 40` crashes (runs 1, 9, 20). Reverted per decision rule (3+ / 40).
  - Task 3: Collected crash samples across 40 runs (5 crashes observed):
    - Samples:
      - Crash 1: `test_catalog_dock.py::test_catalog_context_menu_refresh_schema_emits_binding`
      - Crash 21: `test_catalog_dock.py::test_catalog_context_menu_refresh_schema_emits_binding`
      - Crash 23: `test_actions.py::test_format_action_is_enabled_and_bound`
      - Crash 29: `test_actions.py::test_format_action_is_enabled_and_bound`
      - Crash 34: `test_catalog_dock.py::test_catalog_context_menu_refresh_schema_emits_binding`
    - Analysis:
      1. Last completed test varies (`test_catalog_dock.py` vs `test_actions.py`), but clusters early in the suite (3%-15%).
      2. C stack is identical across all crashes: `_Py_DumpStack` -> `PyQt6/QtCore.abi3.so` -> `QObject::event` -> `QApplicationPrivate::notify_helper` -> `QCoreApplication::notifyInternal2` -> `QCoreApplicationPrivate::sendPostedEvents` -> `QEventDispatcherGlib::processEvents`.
      3. Crashes cluster around widget-heavy tests (`test_actions.py` creating MainWindow/actions, `test_catalog_dock.py` creating CatalogDock).
      4. Isolated execution (`/tmp/wherewolf/flake.sh 40 tests/test_catalog_dock.py` and `tests/test_actions.py`) produced `0 / 40` crashes for both. The crash occurs only during suite-level execution, indicating interaction/teardown event processing under Python coverage tracing.
