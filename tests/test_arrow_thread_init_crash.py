"""Regression guard for the DuckDB->Polars segfault on short-lived worker threads.

pyarrow's bundled mimalloc initialises a thread-local heap the first time libarrow
allocates. If that first allocation happens on a secondary thread, `mi_thread_init`
faults for every *subsequent* thread once the first one exits. The desktop app creates a
fresh QThread per query, so the second query crashed the process (see
docs/plans/2026-08-02_post-rc-defects.md, D1).

The failure is a native SIGSEGV, not a Python exception, so the only way to observe it is
a subprocess exit code.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# The crash lands on the second thread; anything less than 3 cannot observe it.
THREAD_RUNS = 4

CHILD = textwrap.dedent(
    """
    import sys
    import threading
    from pathlib import Path

    # Importing the execution registry is what must make the app crash-safe: it is
    # imported on the main thread at startup and is where the eager pyarrow import lives.
    import wherewolf.execution.registry  # noqa: F401

    import duckdb

    csv_path = sys.argv[1]
    runs = int(sys.argv[2])


    def convert():
        con = duckdb.connect(database=":memory:")
        con.from_csv_auto(csv_path).create_view("t", replace=True)
        frame = con.sql("SELECT * FROM t").limit(50).pl()
        assert len(frame) > 0
        con.close()


    for _ in range(runs):
        # A *fresh, short-lived* thread per conversion is the trigger. Reusing one
        # long-lived thread does not reproduce the crash.
        worker = threading.Thread(target=convert)
        worker.start()
        worker.join()

    print("SURVIVED")
    """
)


@pytest.fixture
def csv_source(tmp_path: Path) -> Path:
    path = tmp_path / "rows.csv"
    lines = ["id,name,value"]
    lines += [f"{i},name_{i},{i * 1.5}" for i in range(200)]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_repeated_short_lived_threads_can_convert_duckdb_to_polars(
    csv_source: Path, tmp_path: Path
) -> None:
    script = tmp_path / "child.py"
    script.write_text(CHILD, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script), str(csv_source), str(THREAD_RUNS)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,  # the whole point is to inspect the exit code, including -11
    )

    assert result.returncode == 0, (
        f"child exited {result.returncode} "
        f"(negative return codes are fatal signals; -11 is the SIGSEGV this guards)\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr[-2000:]}"
    )
    assert "SURVIVED" in result.stdout


def test_registry_import_initialises_arrow_on_the_importing_thread() -> None:
    """The fix is an import-order guarantee, so assert the ordering directly.

    This is a fast proxy for the subprocess test above; it is deliberately not a
    substitute for it.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import wherewolf.execution.registry; print('pyarrow' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "True", (
        "wherewolf.execution.registry must import pyarrow eagerly on the importing "
        "thread so libarrow's mimalloc heap is initialised on the main thread"
    )
