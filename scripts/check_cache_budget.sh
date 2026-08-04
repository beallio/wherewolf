#!/usr/bin/env bash
set -euo pipefail

cache_root="${WHEREWOLF_CACHE_ROOT:-/tmp/wherewolf}"
budget=4294967296

if [[ ! -L "$cache_root" ]]; then
    echo "cache root is not a symlink; it is back on the tmpfs" >&2
    exit 1
fi

resolved_root="$(readlink -f -- "$cache_root")"
du_output="$(du -sb -- "$resolved_root")"
bytes="${du_output%%[[:space:]]*}"
echo "cache bytes: $bytes"

if (( bytes > budget )); then
    echo "cache budget exceeded: $bytes > $budget" >&2
    exit 1
fi
