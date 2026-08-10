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

echo "Creating .env file with secure defaults (you MUST change these!)..."
if [ ! -f .env ]; then
  cat > .env << 'EOF'
# SECURITY WARNING: Change these in production!
DEBUG=False
DJANGO_SECRET_KEY=change-me-in-production-at-least-50-chars
POSTGRES_PASSWORD=change-me-in-production-at-least-20-chars
POSTGRES_USER=django_user
POSTGRES_DB=django_db
POSTGRES_HOST=db
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
EOF
  echo "Created .env file. IMPORTANT: Update POSTGRES_PASSWORD and DJANGO_SECRET_KEY!"
else
  echo ".env file already exists. Skipping creation."
fi

echo "Building Docker images..."
docker compose build

echo "Starting services..."
docker compose up -d

echo "Waiting for database to be ready..."
sleep 5

echo "Applying database migrations..."
docker compose exec -T web sh -c "cd /app/project && python manage.py migrate"

echo "Collecting static files..."
docker compose exec -T web sh -c "cd /app/project && python manage.py collectstatic --noinput"

echo
echo "✓ Setup complete!"
echo
echo "Start the application with:"
echo "  ./run.sh"
echo
echo "View logs with:"
echo "  docker compose logs -f"
echo
echo "Stop with:"
echo "  docker compose down"
