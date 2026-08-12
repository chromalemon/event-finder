#!/usr/bin/env bash

set -eu

export DEBUG="True"
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-dev-test-secret-key-for-django-tests}"
export POSTGRES_DB="${POSTGRES_DB:-django_db}"
export POSTGRES_USER="${POSTGRES_USER:-django_user}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-dev-password-change-me}"
export POSTGRES_HOST="${POSTGRES_HOST:-db}"
export REDIS_URL="${REDIS_URL:-redis://redis:6379/0}"

if [ ! -f .env ]; then
  echo "Creating a local .env file for test runs..."
  cp .env.example .env
fi

docker compose down --remove-orphans --volumes >/dev/null 2>&1 || true

docker compose run --rm \
  -e DEBUG \
  -e DJANGO_SECRET_KEY \
  -e POSTGRES_DB \
  -e POSTGRES_USER \
  -e POSTGRES_PASSWORD \
  -e POSTGRES_HOST \
  -e REDIS_URL \
  web python manage.py test --verbosity 2

