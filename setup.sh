#!/usr/bin/env bash

set -e

echo "Checking prerequisites..."

command -v python3 >/dev/null || {
    echo "Python 3 is required but not installed."
    exit 1
}

command -v docker >/dev/null || {
    echo "Docker is required but not installed."
    exit 1
}

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Applying database migrations..."
cd project
python manage.py migrate
cd ..

echo "Starting Redis..."

if ! docker ps -a --format '{{.Names}}' | grep -q '^redis$'; then
    docker run -d --name redis -p 6379:6379 redis:7
else
    docker start redis >/dev/null
fi

echo "Waiting for Redis..."
until docker exec redis redis-cli PING >/dev/null 2>&1; do
    sleep 1
done

echo
echo "Setup complete!"
echo
echo "Start the application with:"
echo "./run.sh"