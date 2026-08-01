"""Builder for constructing immutable ExecutionRequest snapshots."""

from datetime import datetime
from uuid import uuid4

from wherewolf.domain.enums import EngineKind
from wherewolf.domain.models import ExecutionRequest
from wherewolf.services.catalog_service import CatalogService


class ExecutionRequestBuilder:
    """Constructs frozen ExecutionRequest objects from current application state."""

    @staticmethod
    def build(
        sql: str,
        source_dialect: str,
        engine: EngineKind,
        catalog_service: CatalogService,
        preview_limit: int = 1000,
    ) -> ExecutionRequest:
        cleaned_sql = sql.strip()
        if not cleaned_sql:
            raise ValueError("SQL statement cannot be empty or whitespace-only")

        catalog_snapshot = catalog_service.snapshot()
        submitted_at = datetime.now().astimezone()

        return ExecutionRequest(
            request_id=uuid4(),
            engine=engine,
            source_dialect=source_dialect,
            original_sql=cleaned_sql,
            executable_sql=cleaned_sql,
            catalog=catalog_snapshot,
            preview_limit=preview_limit,
            submitted_at=submitted_at,
        )


__all__ = ["ExecutionRequestBuilder"]
