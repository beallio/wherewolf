import runpy
import sys

import pytest


def test_module_entrypoint_delegates_to_desktop_main(monkeypatch) -> None:
    calls: list[str] = []

    def desktop_main() -> int:
        calls.append("desktop")
        return 23

    monkeypatch.setattr("wherewolf.desktop.application.main", desktop_main)
    # __main__ parses sys.argv, which under pytest is pytest's own command line.
    monkeypatch.setattr(sys, "argv", ["wherewolf"])

    with pytest.raises(SystemExit, match="23"):
        runpy.run_module("wherewolf.__main__", run_name="__main__")

    assert calls == ["desktop"]
