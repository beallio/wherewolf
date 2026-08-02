import importlib.util


def test_streamlit_engine_cache_factory_is_removed() -> None:
    assert importlib.util.find_spec("wherewolf.engines") is None
