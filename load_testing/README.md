# WebSocket load testing

This tests the real authenticated Django Channels endpoint. Run it only against
a local/test deployment you control. It creates test accounts, attendee rows,
sessions, and (when broadcasting) chat messages.

## 1. Seed dedicated test accounts

From the repository root, while the Compose stack is running:

```bash
mkdir -p load_testing
docker compose exec web python /app/load_testing/seed_data.py --users 100
```

The script creates an event and `loadtest_00000` ... `loadtest_00099`
accounts (plus `loadtest_host`). Re-running it reuses those accounts and
creates fresh session cookies. Use `--event-id ID` to target an existing event
instead of creating a new one.

The output file `load_testing/sessions.json` contains authentication cookies.
Do not commit it or share it.

## 2. Install the client dependency

The repository already pins `websockets==15.0.1`. If it is installed in your
local virtualenv:

```bash
.venv/bin/python -m pip show websockets
```

Otherwise install the repository requirements in the active environment.

## 3. Start with a small idle-connection test

```bash
python load_testing/websocket_stress.py --connections 10 --duration 30 --ramp-up 5
```

Then increase gradually:

```bash
python load_testing/websocket_stress.py --connections 50 --duration 30 --ramp-up 10 --output load_testing/results-50.json
python load_testing/websocket_stress.py --connections 100 --duration 60 --ramp-up 15 --output load_testing/results-100.json
python load_testing/websocket_stress.py --connections 250 --duration 60 --ramp-up 20 --output load_testing/results-250.json
```

Seed enough users first. Do not jump straight to a large test.

## 4. Test message fan-out

One client sends 10 messages to the event group; every connected client
should receive each message:

```bash
python load_testing/websocket_stress.py --connections 50 --duration 15 --ramp-up 10 --messages 10 --message-interval 0.2 --output load_testing/broadcast-50.json
```

The reported delivery ratio compares received client-message deliveries with
the expected number of deliveries. This measures group fan-out, not concurrent
publishing by every client.

## 5. Monitor the containers

In a second terminal:

```bash
docker stats
```

For PostgreSQL connection counts:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select state, count(*) from pg_stat_activity group by state;"'
```

For Redis:

```bash
docker compose exec redis redis-cli INFO clients
docker compose exec redis redis-cli INFO memory
```

## Interpretation

- `connected`: client completed the handshake and received the consumer's
  initial history frame.
- `connection_latency`: time from client connect attempt to initial frame.
- `active_at_end_of_idle_phase`: clients that reached the history frame.
- `delivery_ratio`: received message deliveries divided by expected deliveries.
- `delivery_latency`: measured from send to each client's receipt, on the same
  load-generator process.

Run tests from a separate machine for more meaningful capacity measurements
than running the generator and server on the same host. A single Uvicorn worker
is currently configured; keep that constant for the baseline and change one
variable at a time.

The script is an initial benchmark harness, not a production-grade distributed
load generator. Its load-generator CPU and file-descriptor limits can become
the bottleneck at high connection counts.
