from __future__ import annotations

import pytest


def test_spark_tests_are_opt_in(pytestconfig: pytest.Config) -> None:
    assert "not spark" in pytestconfig.getini("addopts")
    assert any(marker.startswith("spark:") for marker in pytestconfig.getini("markers"))
