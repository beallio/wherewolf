# SQL Completion

Wherewolf SQL completion is deterministic and case-insensitive. It ranks a label against the
typed identifier in this order:

1. exact match;
2. prefix match;
3. token-initial match across underscores, hyphens, whitespace, and camel-case boundaries;
4. contiguous substring match;
5. bounded ordered-subsequence match.

The bounded subsequence rule intentionally rejects broad matches with excessive gaps. A forced
empty-prefix request remains available and uses semantic then alphabetical ordering. Results are
deduplicated case-insensitively after ranking and capped at 100 candidates.

## Scope and aliases

Completion only reads the statement containing the cursor. In expression contexts it offers
visible `FROM` and `JOIN` relation aliases, while a qualified expression such as `o.rev` is
limited to columns from the resolved relation. Relation aliases are not offered as new table
sources in `FROM` or `JOIN` contexts.

SELECT expression aliases are available in `ORDER BY`. DuckDB completion also exposes a
non-aggregate alias in `WHERE` and `GROUP BY`, an aggregate alias in `HAVING`, and a window alias
in `QUALIFY`. They are not offered in `JOIN ON`, and an alias later in the same SELECT list is not
treated as a lateral alias.

## Function metadata

DuckDB completion reads and caches identifier-shaped functions from a fresh local
`duckdb_functions()` connection. Expression positions use scalar, aggregate, and macro functions;
table-reference positions use table and table-macro functions. Curated signatures override dynamic
ones when available, and metadata failures leave the curated fallback usable.

Spark completion remains non-blocking. Selecting an available Spark execution engine immediately
uses its curated fallback and begins one background discovery of built-ins from an isolated child
session in the local Wherewolf Spark runtime. A successful result is cached for future completion;
a failure keeps the curated fallback. “Comprehensive” means local built-ins from that isolated
runtime, not remote catalogs, cluster functions, extensions requiring non-default configuration,
or persistent user-defined functions. Switching engines never changes an already-visible list.

## Non-goals

Completion does not provide edit-distance spelling correction, persistent DuckDB macros or UDFs,
Spark temporary UDFs, remote Spark Connect or cluster catalogs, vendor-specific Azure SQL, Oracle,
or PostgreSQL function catalogs, or full support for deeply correlated nested scopes.
