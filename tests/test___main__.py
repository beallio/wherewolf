import runpy

import pytest

import wherewolf.cli


def test_module_entrypoint_delegates_to_desktop_main(monkeypatch) -> None:
    calls: list[str] = []

    def desktop_main() -> int:
        calls.append("desktop")
        return 23

    monkeypatch.setattr(wherewolf.cli, "desktop_main", desktop_main)

    with pytest.raises(SystemExit, match="23"):
        runpy.run_module("wherewolf.__main__", run_name="__main__")

    assert calls == ["desktop"]
