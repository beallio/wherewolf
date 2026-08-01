#!/usr/bin/env bash
# Runs the pytest suite under coverage N times (default 20) to check for native Qt/coverage crashes.
set -euo pipefail

runs="${1:-20}"
cd "$(git rev-parse --show-toplevel)"

echo "Running pytest suite ${runs} times under coverage..."
crashes=0

for i in $(seq 1 "$runs"); do
  status=0
  ./run.sh uv run pytest -q >/tmp/wherewolf/flake-guard-last.txt 2>&1 || status=$?
  if [ "$status" -ne 0 ]; then
    if [ "$status" -gt 128 ] || grep -qE "Fatal Python error|Segmentation fault" /tmp/wherewolf/flake-guard-last.txt; then
      crashes=$((crashes+1))
      echo "  CRASH detected on run $i! (exit code $status)"
    else
      echo "  ORDINARY TEST FAILURE detected on run $i (not a native crash, exit code $status):"
      tail -20 /tmp/wherewolf/flake-guard-last.txt
      exit 2
    fi
  fi
done

if [ "$crashes" -gt 0 ]; then
  echo "FAILED: Detected $crashes native crash(es) in $runs runs."
  exit 1
fi

echo "PASSED: 0 native crashes in $runs runs."
exit 0
