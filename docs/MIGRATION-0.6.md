# Migrating from 0.5.x to 0.6.0

## Native desktop application

`wherewolf` no longer starts a browser-based interface. It opens the native PyQt6 desktop window;
`wherewolf-desktop` is an equivalent command. There is no local web server to visit after launch.

Move the existing file-query workflow into the desktop window: add files through **Add
Datasets…** or drag and drop, write SQL in the editor, and view results in the grid.

## Query history

Existing `~/.wherewolf/history.json` files are kept. On the first read, valid version-1 entries
are migrated in place to version 2: their existing order and query data are retained, and each
entry receives a stable ID and catalog representation. The migration is one-time; malformed
entries remain unreadable rather than being guessed at or rewritten as valid history.

## Spark is optional

PySpark is no longer installed by default. DuckDB remains the default engine and a default
installation does not import PySpark. To use the local Spark engine, install the optional extra
and a Java runtime compatible with PySpark:

```bash
uv tool install 'wherewolf[spark]'
```

From a source checkout, run `./run.sh uv sync --extra spark` after Java is available.

## Python requirement

Wherewolf 0.6.0 requires Python 3.12 or newer. Python 3.11 is not supported.

## License

0.6.0 is GPL-3.0-only. MIT grants for releases through 0.5.2 remain valid and their original text
is retained in `LICENSES/MIT-pre-0.6.txt`.
