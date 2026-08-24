"""Lazy, process-local Spark runtime shared by execution and metadata discovery."""

from __future__ import annotations

from importlib import import_module
from threading import Lock
from typing import Any

_ROOT_SESSION: Any | None = None
_ROOT_SESSION_LOCK = Lock()


def _build_root_session() -> Any:
    spark_session = import_module("pyspark.sql").SparkSession
    return (
        # pyspark exposes ``builder`` dynamically, which ty cannot resolve.
        spark_session.builder.appName("Wherewolf")  # ty: ignore[unresolved-attribute]
        .master("local[1]")
        .config("spark.driver.memory", "512m")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .getOrCreate()
    )


def create_child_session() -> Any:
    """Return an isolated SQL child session while retaining one JVM-backed root context."""

    global _ROOT_SESSION
    with _ROOT_SESSION_LOCK:
        if _ROOT_SESSION is None:
            _ROOT_SESSION = _build_root_session()
        return _ROOT_SESSION.newSession()


def reset_spark_runtime_for_tests() -> None:
    """Forget the cached root reference without stopping a shared Spark context."""

    global _ROOT_SESSION
    with _ROOT_SESSION_LOCK:
        _ROOT_SESSION = None


__all__ = ["create_child_session", "reset_spark_runtime_for_tests"]
