"""Builder for constructing immutable ExecutionRequest snapshots."""

import re
from datetime import datetime
from uuid import uuid4

from wherewolf.domain.enums import EngineKind
from wherewolf.domain.errors import TranslationError
from wherewolf.domain.models import ExecutionRequest, SourceSnapshot
from wherewolf.services.catalog_service import CatalogService
from wherewolf.translation.translator import Translator

_ORACLE_UNSUPPORTED_CONSTRUCTS = (
    ("ROWNUM", re.compile(r"\bROWNUM\b", re.IGNORECASE)),
    ("DUAL", re.compile(r"\bFROM\s+DUAL\b", re.IGNORECASE)),
)


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

        unsupported_construct = _unsupported_oracle_construct(cleaned_sql, source_dialect)
        if unsupported_construct is not None:
            raise TranslationError(
                f"Oracle construct {unsupported_construct} cannot run against the selected local engine. "
                "Rewrite the query without it before running."
            )

        catalog_snapshot = catalog_service.snapshot()
        submitted_at = datetime.now().astimezone()

        target_dialect = engine.value
        if source_dialect.lower() != target_dialect.lower():
            translator = Translator()
            statements = translator.translate_statements(
                cleaned_sql, from_dialect=source_dialect, to_dialect=target_dialect
            )
            executable_sql = ";\n\n".join(statements)
        else:
            executable_sql = cleaned_sql

        return ExecutionRequest(
            request_id=uuid4(),
            engine=engine,
            source_dialect=source_dialect,
            original_sql=cleaned_sql,
            executable_sql=executable_sql,
            catalog=catalog_snapshot,
            preview_limit=preview_limit,
            submitted_at=submitted_at,
            source_snapshots=tuple(
                SourceSnapshot(
                    path=binding.path,
                    size=_stat_or_none(binding.path, "st_size"),
                    mtime_ns=_stat_or_none(binding.path, "st_mtime_ns"),
                )
                for binding in catalog_snapshot
            ),
        )


def _stat_or_none(path, field: str) -> int | None:
    try:
        return int(getattr(path.stat(), field))
    except OSError:
        return None


def _unsupported_oracle_construct(sql: str, source_dialect: str) -> str | None:
    if source_dialect.lower() != "oracle":
        return None

    return next(
        (construct for construct, pattern in _ORACLE_UNSUPPORTED_CONSTRUCTS if pattern.search(sql)),
        None,
    )


__all__ = ["ExecutionRequestBuilder"]
