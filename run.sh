#!/usr/bin/env bash

set -eu

echo "Checking prerequisites..."

command -v docker >/dev/null || {
  echo "Docker is required but not installed."
  exit 1
}

docker compose version >/dev/null 2>&1 || {
  echo "Docker Compose is required but not installed."
  exit 1
}

echo "Creating .env file with local development defaults..."
if [ ! -f .env ]; then
  cat > .env << 'EOF'
# Local development defaults; change before deploying to production.
DEBUG=True
DJANGO_SECRET_KEY=dev-secret-key-change-me-before-production
POSTGRES_PASSWORD=dev-password-change-me
POSTGRES_USER=django_user
POSTGRES_DB=django_db
POSTGRES_HOST=db
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://0.0.0.0:8000
REDIS_URL=redis://redis:6379/0
EOF
  echo "Created .env with local defaults. Update the values before production use."
else
  echo ".env file already exists. Skipping creation."
fi

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

echo "Resetting any stale Docker containers..."
docker compose down --remove-orphans --volumes >/dev/null 2>&1 || true

echo "Building Docker images..."
docker compose build

echo "Starting services..."
docker compose up -d --force-recreate

echo "Waiting for database to be ready..."
sleep 5

echo "Applying database migrations..."
docker compose exec -T web sh -c "cd /app/project && python manage.py migrate --noinput"

if [ "${DEBUG,,}" = "false" ]; then
    echo "Collecting static files..."
    docker compose exec -T web sh -c "cd /app/project && python manage.py collectstatic --noinput"
fi

echo
echo "✓ Setup complete!"
echo
echo "✓ Application started successfully!"
echo "  Access at: http://localhost:8000"
echo
echo "View logs with:"
echo "  docker compose logs -f"
echo
echo "Stop with:"
echo "  docker compose down"
