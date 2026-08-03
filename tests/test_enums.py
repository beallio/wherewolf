from enum import StrEnum

from wherewolf.domain import CompletionKind, EngineKind, SourceFormat


def test_enums_are_str_enums() -> None:
    assert issubclass(EngineKind, StrEnum)
    assert issubclass(SourceFormat, StrEnum)
    assert issubclass(CompletionKind, StrEnum)


def test_source_format_members() -> None:
    assert [fmt.value for fmt in SourceFormat] == ["csv", "parquet", "json", "jsonl", "xlsx"]
