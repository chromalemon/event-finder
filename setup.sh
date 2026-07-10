#!/usr/bin/env bash

set -e

echo "Checking prerequisites..."

command -v docker >/dev/null || {
    echo "Docker is required but not installed."
    exit 1
}

docker compose version >/dev/null 2>&1 || {
    echo "Docker Compose is required but not installed."
    exit 1
}

echo "Building Docker images..."
docker compose build

echo "Applying database migrations inside the web container..."
docker compose run --rm web python manage.py migrate

echo
echo "Setup complete!"
echo
echo "Start the application with:"
echo "./run.sh"