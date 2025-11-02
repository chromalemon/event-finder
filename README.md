Event Finder is a webapp which integrates messaging into the event discovery and creation theme.

### Create & activate virtual env
python -m venv .venv
.venv\Scripts\activate # Windows
# or
source .venv/bin/activate # macOS/Linux/Codespaces

### Install dependencies
pip install -r requirements.txt
# (If you do not have one yet, run:)
pip install django channels daphne channels-redis uvicorn websockets
pip freeze > requirements.txt

### Database migrations & admin
cd project
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser # create an admin for testing

### (If using Redis locally) start and verify
docker rm -f redis 2>/dev/null || true
docker run -p 6379:6379 --name redis -d redis:7
docker exec -it redis redis-cli PING

### Run the dev server (options)
Note: Channels requires an ASGI server. Use uvicorn (with reload) for fast dev iterations, or daphne/runserver as alternatives.

Recommended — uvicorn (auto-reload + WebSockets)
export DJANGO_SETTINGS_MODULE=event_finder.settings
uvicorn event_finder.asgi:application --reload --host 0.0.0.0 --port 8000

Alternative — daphne (explicit ASGI)
export DJANGO_SETTINGS_MODULE=event_finder.settings
daphne -b 0.0.0.0 -p 8000 event_finder.asgi:application

Simple Django dev server (may not behave identically for WebSockets in all setups)
cd project
python manage.py runserver 0.0.0.0:8000

Visit http://127.0.0.1:8000 (or forwarded Codespaces port)

### Stop / restart helper commands
# Stop a foreground server: Ctrl+C in its terminal.

# Kill any existing uvicorn/daphne processes and start uvicorn in background (fast restart)
pkill -f "uvicorn.*event_finder.asgi" 2>/dev/null || true
pkill -f "daphne.*event_finder.asgi" 2>/dev/null || true
export DJANGO_SETTINGS_MODULE=event_finder.settings
uvicorn event_finder.asgi:application --reload --host 0.0.0.0 --port 8000 & disown

# Helper function (add to your shell session or ~/.bashrc for convenience)
restart_server() {
  pkill -f "uvicorn.*event_finder.asgi" 2>/dev/null || true
  pkill -f "daphne.*event_finder.asgi" 2>/dev/null || true
  export DJANGO_SETTINGS_MODULE=event_finder.settings
  uvicorn event_finder.asgi:application --reload --host 0.0.0.0 --port 8000 & disown
}

# To run daphne in background instead:
pkill -f "daphne.*event_finder.asgi" 2>/dev/null || true
export DJANGO_SETTINGS_MODULE=event_finder.settings
daphne -b 0.0.0.0 -p 8000 event_finder.asgi:application & disown

### Quick checks
# Ensure Redis is reachable (Channels CHANNEL_LAYERS config points to redis://localhost:6379)
docker exec -it redis redis-cli PING   # should return PONG

# Confirm ASGI routing is active (server logs show websocket connect attempts)
# If WebSocket connections return 403/404, check CSRF_TRUSTED_ORIGINS, ALLOWED_HOSTS, and routing.

### Notes
- Use uvicorn for fast autoreload while developing websocket features.
- Keep Redis running while testing Channels.
- Remove background processes with pkill if ports appear occupied.

### kill all
# stop runserver, uvicorn, daphne and any stray python manage.py runserver
pkill -f "manage.py runserver" 2>/dev/null || true
pkill -f "uvicorn.*event_finder.asgi" 2>/dev/null || true
pkill -f "daphne.*event_finder.asgi" 2>/dev/null || true

# verify none are running
ps aux | egrep "(runserver|uvicorn|daphne)" | egrep -v "egrep" || true

# stop & remove container named "redis"
docker stop redis 2>/dev/null || true
docker rm -f redis 2>/dev/null || true

# verify no redis on port 6379
ss -ltnp | grep 6379 || true

# show what's listening
ss -ltnp | egrep ":8000|:6379" || true

# if you find a PID and need to force-kill:
# sudo kill -9 <PID>

deactivate 2>/dev/null || true
exit

# no python/asgi servers
ps aux | egrep "(runserver|uvicorn|daphne|python)" | egrep -v "egrep" || true

# no redis listening
ss -ltnp | grep 6379 || true

