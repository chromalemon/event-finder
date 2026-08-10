#!/usr/bin/env bash

set -e

docker compose up --build --pull always -d

echo "Waiting for database to be ready..."
sleep 5

echo "Running database migrations..."
docker compose exec -T web sh -c "cd /app/project && python manage.py migrate"

echo "Collecting static files..."
docker compose exec -T web sh -c "cd /app/project && python manage.py collectstatic --noinput"

echo
echo "✓ Application started successfully!"
echo "  Access at: http://localhost:8000"
echo "  Static files collected to: /app/project/staticfiles/"
echo
echo "To view logs: docker compose logs -f web"
echo "To stop:      docker compose down"