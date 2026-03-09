#!/usr/bin/env bash
export UV_PROJECT_ENVIRONMENT=/tmp/wherewolf/.venv
export XDG_CACHE_HOME=/tmp/wherewolf/.cache
export PYTHONPYCACHEPREFIX=/tmp/wherewolf/__pycache__

echo "Using environment: /tmp/wherewolf/.venv"
exec "$@"
