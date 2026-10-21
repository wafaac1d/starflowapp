#!/bin/sh
set -eu
if [ "${WEB_CONCURRENCY:-1}" != "1" ]; then
  echo "WEB_CONCURRENCY must be 1" >&2
  exit 1
fi
alembic upgrade head
exec uvicorn starflow.asgi:create_app --factory --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --workers 1
