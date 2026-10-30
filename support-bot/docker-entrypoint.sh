#!/bin/sh
set -eu

attempt=1
max_attempts=30

until alembic upgrade head; do
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "Migration failed after ${max_attempts} attempts"
    exit 1
  fi
  echo "Migration attempt ${attempt}/${max_attempts} failed, waiting for database..."
  attempt=$((attempt + 1))
  sleep 2
done

exec uvicorn src.main:app --host 0.0.0.0 --port 8000
