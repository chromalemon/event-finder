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


## 6. Concurrent publishers and fan-out contention

The extended harness can have multiple connected clients publish at the same
time. Each publisher sends `--messages` messages; this is **per publisher**.
Messages have unique IDs, and the harness tracks each unique
(recipient, message) pair, reporting missing and duplicate deliveries.

Start with a controlled 500-client workload:

```bash
.venv/bin/python load_testing/websocket_stress.py \
    --connections 500 \
    --duration 15 \
    --ramp-up 30 \
    --publishers 10 \
    --messages 10 \
    --message-interval 0.2 \
    --output load_testing/concurrent-500x10.json
```

This attempts 100 messages from 10 publishers and expects up to 50,000
client-message deliveries if all 500 clients remain connected and all 100
messages are published. The report records the actual successful publishes
and uses those to calculate the expected-delivery denominator. Monitor
`docker stats` during the run. Do not run against a public or third-party
deployment.

Useful fields include:

- `messages_published`: successful WebSocket sends from publisher clients.
- `expected_deliveries`: successfully published messages multiplied by the
  connected-recipient snapshot taken before publishing.
- `unique_received_deliveries`: unique recipient/message pairs received.
- `missing_deliveries` and `duplicate_deliveries`: loss and duplicate counts.
- `delivery_latency`: end-to-end client-observed fan-out latency.
- `published_messages_per_second`: publisher send rate.
- `delivered_fanout_events_per_second`: observed unique deliveries divided
  by broadcast elapsed time. This is a fan-out event rate, not messages/sec.

## 7. Generate a benchmark report for your CV

Pass the saved JSON files from your runs to the report generator. It supports
both the original single-publisher output and the concurrent-publisher schema:

```bash
.venv/bin/python load_testing/summarise_results.py \
    load_testing/results-100.json \
    load_testing/results-250.json \
    load_testing/results-500.json \
    load_testing/broadcast-250.json \
    load_testing/broadcast-500.json \
    load_testing/concurrent-500x10.json \
    --output load_testing/benchmark-report.md
```

The Markdown report compares runs, identifies the highest clean connection
result and largest fully delivered broadcast workload, and drafts a quantified
CV bullet only when the supplied evidence supports it. Keep the original JSON
files as supporting benchmark data. The generated bullet must describe the
tested workload accurately; do not present a local benchmark as production
capacity or claim sustained throughput from a short burst test.


## 8. Verify database persistence

The chat consumer broadcasts even if its database save raises an exception.
Consequently, successful WebSocket delivery alone does **not** prove messages
were persisted. The stress harness records every successfully published
unique marker. Verify those markers against PostgreSQL from inside the web
container after the concurrent-publisher test:

```bash
docker compose exec web python /app/load_testing/verify_chat_persistence.py \
    --results /app/load_testing/concurrent-500x10.json
```

The verifier checks the exact event and published message contents, reports
missing messages and duplicate database rows, and adds a `persistence`
section to the same JSON result. This closes an important gap between
real-time fan-out and durable chat-message storage.

Regenerate the Markdown report after persistence verification so the CV
evidence includes database persistence only when it has actually been checked.

## 9. Diagnose WebSocket connection latency

The ASGI application now emits one structured timing record for each WebSocket
connection attempt. Restart the web service after pulling the changes so the
updated ASGI application and logging configuration are loaded:

```bash
docker compose restart web
```

Run the load test from the load-generator machine as usual. In another terminal,
inspect the server-side timings:

```bash
docker compose logs --since 10m web | grep 'chat_websocket_connect_timing'
```

Each record contains these fields (all durations are milliseconds):

- `auth_middleware_ms`: Channels cookie, session, and authentication middleware
  setup, measured before the consumer is called. With the database-backed
  session engine, this includes session retrieval and user loading.
- `authorisation_ms`: event lookup and attendee authorisation in PostgreSQL.
- `group_add_ms`: Redis channel-layer group registration.
- `accept_ms`: time for the consumer to issue the WebSocket accept.
- `history_query_and_serialisation_ms`: recent-message query and conversion
  into the initial history payload.
- `history_send_ms`: time for the ASGI consumer to send the initial history
  frame.
- `consumer_connect_total_ms`: total time spent inside the consumer's
  `connect()` method.
- `outcome`: whether the consumer accepted or rejected the connection.

Compare the distributions of these server-side values across the 250 records
with the load tester's client-side `connection_latency`. The client-side value
also includes network, TLS/proxy, WebSocket handshake, and scheduling overhead;
it is not expected to equal the sum of the server-side timings exactly.

The timing log is diagnostic instrumentation, not a benchmark in itself. Keep
it enabled for diagnosis, but be aware that emitting one log record per
connection adds a small amount of work during large tests.
