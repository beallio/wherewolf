#!/usr/bin/env bash
export UV_PROJECT_ENVIRONMENT=/tmp/wherewolf/.venv
export XDG_CACHE_HOME=/tmp/wherewolf/.cache
export PYTHONPYCACHEPREFIX=/tmp/wherewolf/__pycache__
export PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"

echo "Using environment: $UV_PROJECT_ENVIRONMENT"
exec "$@"
