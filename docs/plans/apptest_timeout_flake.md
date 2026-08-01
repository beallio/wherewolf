# AppTest Timeout Flake

## Problem Definition

`streamlit.testing.v1.AppTest.from_file()` defaults to a three-second script
timeout. On loaded CI runners, the full Streamlit script can exceed that
budget even when the application is healthy.

## Architecture Overview

Keep the change in test infrastructure. Define one `APPTEST_TIMEOUT` constant
in `tests/conftest.py` and pass it to every existing `AppTest.from_file()`
call site through the verified `default_timeout` parameter.

## Core Data Structures

- `APPTEST_TIMEOUT: int = 30`: the single test-run timeout in seconds.

## Public Interfaces

No application or package interfaces change. Only test setup imports the
shared timeout constant.

## Dependency Requirements

The installed Streamlit signature was verified as
`AppTest.from_file(script_path, *, default_timeout: float = 3)`.

## Testing Strategy

First make an existing AppTest test fail by referencing the not-yet-defined
shared constant. Then define the constant and route all 13 call sites through
it. Run both requested full pytest commands, restore Python 3.14, run quality
gates, and use grep to confirm the complete call-site coverage.
