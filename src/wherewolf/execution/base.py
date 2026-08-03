from typing import Protocol, runtime_checkable
from uuid import UUID

from wherewolf.domain.models import (
    CatalogEntry,
    ExecutionRequest,
    ProfileResult,
    QueryResult,
    SchemaResult,
)


@runtime_checkable
class CancellationHandle(Protocol):
    @property
    def request_id(self) -> UUID: ...

    def cancel(self) -> bool: ...


@runtime_checkable
class ExecutionEngine(Protocol):
    def execute_preview(self, request: ExecutionRequest) -> QueryResult: ...

    def inspect_schema(self, entry: CatalogEntry) -> SchemaResult: ...

    def profile_dataset(self, entry: CatalogEntry) -> ProfileResult: ...

    def cancellation_handle(self) -> CancellationHandle: ...

    def close(self) -> None: ...
