"""View model for SQL translation across dialects."""

from dataclasses import dataclass

from wherewolf.domain.errors import TranslationError
from wherewolf.domain.models import SqlDiagnostic
from wherewolf.translation.translator import Translator


@dataclass(frozen=True, slots=True)
class TranslationResult:
    translated_sql: str
    diagnostics: tuple[SqlDiagnostic, ...]


def translate_sql_view(query: str, from_dialect: str, to_dialect: str) -> TranslationResult:
    """Translates SQL query string for display in the translation panel.

    Preserves all statements by using `translate_statements`. Returns a `TranslationResult`
    containing translated SQL and any diagnostics generated during translation.

    Args:
        query: Source SQL query.
        from_dialect: Source dialect (e.g. 'duckdb').
        to_dialect: Target engine dialect (e.g. 'spark').

    Returns:
        TranslationResult containing translated SQL and diagnostics tuple.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return TranslationResult(translated_sql="", diagnostics=())

    if from_dialect.lower() == to_dialect.lower():
        return TranslationResult(translated_sql=cleaned_query, diagnostics=())

    try:
        translator = Translator()
        statements = translator.translate_statements(
            cleaned_query, from_dialect=from_dialect, to_dialect=to_dialect
        )
        translated_text = ";\n\n".join(statements)
        return TranslationResult(translated_sql=translated_text, diagnostics=())
    except (TranslationError, ValueError, Exception) as exc:  # noqa: BLE001
        diagnostic = SqlDiagnostic(
            message=str(exc),
            severity="error",
            start_line=1,
            start_column=1,
        )
        return TranslationResult(translated_sql=cleaned_query, diagnostics=(diagnostic,))
