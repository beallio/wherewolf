import streamlit as st
from wherewolf.execution import DuckDBEngine, SparkEngine


@st.cache_resource
def get_duckdb_engine():
    return DuckDBEngine()


@st.cache_resource
def get_spark_engine():
    return SparkEngine()


_ENGINE_GETTERS = {"DuckDB": get_duckdb_engine, "Spark": get_spark_engine}


def get_engine(engine_name: str):
    """Return the cached singleton engine for a UI engine name."""
    if engine_name not in _ENGINE_GETTERS:
        raise ValueError(f"Unknown engine: {engine_name}")
    return _ENGINE_GETTERS[engine_name]()
