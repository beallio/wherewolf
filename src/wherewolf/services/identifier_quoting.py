"""SQL identifier quoting utilities."""

import re

# Standard SQL reserved keywords that require quoting when used as identifiers.
RESERVED_KEYWORDS = {
    "add",
    "all",
    "alter",
    "and",
    "any",
    "as",
    "asc",
    "between",
    "by",
    "case",
    "cast",
    "check",
    "column",
    "constraint",
    "create",
    "cross",
    "current",
    "default",
    "delete",
    "desc",
    "distinct",
    "drop",
    "else",
    "end",
    "except",
    "exists",
    "false",
    "following",
    "for",
    "foreign",
    "from",
    "full",
    "group",
    "having",
    "if",
    "in",
    "index",
    "inner",
    "insert",
    "intersect",
    "into",
    "is",
    "join",
    "key",
    "left",
    "like",
    "limit",
    "not",
    "null",
    "offset",
    "on",
    "or",
    "order",
    "outer",
    "over",
    "partition",
    "preceding",
    "primary",
    "range",
    "references",
    "right",
    "row",
    "rows",
    "select",
    "set",
    "table",
    "then",
    "to",
    "true",
    "union",
    "unique",
    "unbounded",
    "update",
    "using",
    "values",
    "view",
    "when",
    "where",
    "with",
}

_PLAIN_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def quote_identifier(name: str, quote_char: str = '"') -> str:
    """Quotes a SQL identifier if necessary.

    An identifier is kept bare if it consists only of lowercase letters,
    digits, and underscores, starts with a letter or underscore, and is not a
    reserved keyword.

    Embedded quote characters are escaped by doubling them (e.g. `col"name` -> `"col""name"`).

    Args:
        name: The identifier name to quote.
        quote_char: The quote character to use (default double quote `"`)

    Returns:
        The identifier, quoted if needed.
    """
    if _PLAIN_IDENTIFIER_RE.match(name) and name.lower() not in RESERVED_KEYWORDS:
        return name

    escaped_name = name.replace(quote_char, quote_char + quote_char)
    return f"{quote_char}{escaped_name}{quote_char}"
