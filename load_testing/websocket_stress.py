"""Authenticated Django Channels WebSocket concurrency/load tester."""
import argparse
import asyncio
import json
import math
import statistics
import time
import uuid
from collections import Counter
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    index = min(math.ceil((p / 100) * len(ordered)) - 1, len(ordered) - 1)
    return ordered[max(index, 0)]


def summary(values):
    if not values:
        return {
            "min_ms": None, "mean_ms": None, "p50_ms": None,
            "p95_ms": None, "p99_ms": None, "max_ms": None,
        }
    return {
        "min_ms": round(min(values), 2),
        "mean_ms": round(statistics.fmean(values), 2),
        "p50_ms": round(percentile(values, 50), 2),
        "p95_ms": round(percentile(values, 95), 2),
        "p99_ms": round(percentile(values, 99), 2),
        "max_ms": round(max(values), 2),
    }


def distribution(values):
    if not values:
        return {"min": 0, "mean": 0, "max": 0}
    return {
        "min": min(values),
        "mean": round(statistics.fmean(values), 2),
        "max": max(values),
    }


async def run(args):
    data = json.loads(Path(args.sessions).read_text(encoding="utf-8"))
    users = data["users"][:args.connections]
    if len(users) < args.connections:
        raise SystemExit(
            f"Only {len(users)} sessions available; requested {args.connections}. "
            "Run seed_data.py with more --users."
        )

    uri = args.url.rstrip("/") + data["websocket_path"]
    outcomes = Counter()
    connect_ms = []
    active = set()
    unexpected = []
    delivery_ms = []
    sockets = [None] * len(users)

    # A marker is unique to one publishing client and one message. A delivery
    # is counted once per (recipient, marker), so duplicates are measurable.
    sent_at = {}
    received_pairs = set()
    duplicate_deliveries = 0

    async def worker(index, user):
        nonlocal duplicate_deliveries
        cookie = f"sessionid={user['sessionid']}"
        if args.ramp_up:
            await asyncio.sleep(index * args.ramp_up / args.connections)
        started = time.perf_counter()
        connected = False
        try:
            async with connect(
                uri,
                additional_headers={"Cookie": cookie},
                open_timeout=args.open_timeout,
                close_timeout=5,
                ping_interval=20,
                ping_timeout=20,
                max_size=2**20,
            ) as ws:
                sockets[index] = ws
                first = await asyncio.wait_for(ws.recv(), timeout=args.open_timeout)
                connect_ms.append((time.perf_counter() - started) * 1000)
                first_data = json.loads(first)
                if first_data.get("type") != "history":
                    outcomes["unexpected_initial_frame"] += 1
                outcomes["connected"] += 1
                connected = True
                active.add(index)

                while True:
                    raw = await ws.recv()
                    payload = json.loads(raw)
                    if payload.get("type") != "message":
                        continue
                    marker = payload.get("message", "")
                    sent_ns = sent_at.get(marker)
                    if sent_ns is None:
                        continue
                    pair = (index, marker)
                    if pair in received_pairs:
                        duplicate_deliveries += 1
                        continue
                    received_pairs.add(pair)
                    delivery_ms.append(
                        (time.perf_counter_ns() - sent_ns) / 1_000_000
                    )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            outcomes["timeout"] += 1
        except ConnectionClosed as exc:
            if connected:
                unexpected.append({"user": user["username"], "code": exc.code})
                outcomes["closed"] += 1
        except Exception as exc:
            outcomes["error"] += 1
            if len(unexpected) < 20:
                unexpected.append({"user": user["username"], "error": repr(exc)})
        finally:
            active.discard(index)

    tasks = [
        asyncio.create_task(worker(i, user))
        for i, user in enumerate(users)
    ]

    # Wait for the staggered connection attempts, then hold the connections.
    if args.ramp_up:
        await asyncio.sleep(args.ramp_up)
    else:
        await asyncio.sleep(0)
    idle_deadline = time.perf_counter() + args.duration
    while time.perf_counter() < idle_deadline:
        await asyncio.sleep(min(0.25, max(0, idle_deadline - time.perf_counter())))

    active_at_broadcast = sorted(active)
    messages_published = 0
    messages_attempted = 0
    publish_errors = []
    publish_duration_ms = None
    broadcast_elapsed_ms = None
    expected_deliveries = 0

    if args.messages and active_at_broadcast:
        publisher_indices = active_at_broadcast[:min(
            args.publishers, len(active_at_broadcast)
        )]
        gate = asyncio.Event()

        async def publish(publisher_number, client_index):
            nonlocal messages_attempted, messages_published
            await gate.wait()
            ws = sockets[client_index]
            for sequence in range(args.messages):
                marker = (
                    f"loadtest:{uuid.uuid4().hex}:"
                    f"{publisher_number}:{sequence}"
                )
                sent_at[marker] = time.perf_counter_ns()
                messages_attempted += 1
                try:
                    await ws.send(json.dumps({"message": marker}))
                    messages_published += 1
                except Exception as exc:
                    if len(publish_errors) < 20:
                        publish_errors.append({
                            "publisher": client_index,
                            "message": marker,
                            "error": repr(exc),
                        })
                    break
                if args.message_interval:
                    await asyncio.sleep(args.message_interval)

        broadcast_started = time.perf_counter()
        publisher_tasks = [
            asyncio.create_task(publish(number, index))
            for number, index in enumerate(publisher_indices)
        ]
        gate.set()
        await asyncio.gather(*publisher_tasks, return_exceptions=True)
        publish_duration_ms = (time.perf_counter() - broadcast_started) * 1000

        published_markers = [
            marker for marker in sent_at
            if marker.startswith("loadtest:")
        ]
        expected_deliveries = len(active_at_broadcast) * len(published_markers)
        wait_until = time.perf_counter() + args.broadcast_timeout
        while time.perf_counter() < wait_until:
            if len(received_pairs) >= expected_deliveries:
                break
            await asyncio.sleep(0.025)
        broadcast_elapsed_ms = (time.perf_counter() - broadcast_started) * 1000

    active_after_broadcast = sorted(active)
    actual_deliveries = len(received_pairs)
    missing_deliveries = max(0, expected_deliveries - actual_deliveries)
    per_client_counts = [
        sum(1 for recipient, _ in received_pairs if recipient == index)
        for index in active_at_broadcast
    ]
    elapsed_seconds = (broadcast_elapsed_ms or 0) / 1000
    publish_seconds = (publish_duration_ms or 0) / 1000

    report = {
        "test": {
            "target_connections": args.connections,
            "duration_seconds": args.duration,
            "ramp_up_seconds": args.ramp_up,
            "publishers_requested": args.publishers,
            "publishers_active": min(args.publishers, len(active_at_broadcast)),
            "messages_per_publisher": args.messages,
            "message_interval_seconds": args.message_interval,
            "broadcast_timeout_seconds": args.broadcast_timeout,
        },
        "connections": {
            "connected": outcomes["connected"],
            "failed_or_rejected": args.connections - outcomes["connected"],
            "unexpected_closures": outcomes["closed"],
            "timeouts": outcomes["timeout"],
            "other_errors": outcomes["error"],
            "active_at_end_of_idle_phase": len(active_at_broadcast),
            "active_at_end_of_broadcast": len(active_after_broadcast),
            "connection_latency": summary(connect_ms),
        },
        "broadcast": {
            "messages_attempted": messages_attempted,
            "messages_published": messages_published,
            "expected_deliveries": expected_deliveries,
            "unique_received_deliveries": actual_deliveries,
            "missing_deliveries": missing_deliveries,
            "duplicate_deliveries": duplicate_deliveries,
            "delivery_ratio": (
                round(actual_deliveries / expected_deliveries, 6)
                if expected_deliveries else None
            ),
            "delivery_latency": summary(delivery_ms),
            "publish_duration_ms": (
                round(publish_duration_ms, 2)
                if publish_duration_ms is not None else None
            ),
            "broadcast_elapsed_ms": (
                round(broadcast_elapsed_ms, 2)
                if broadcast_elapsed_ms is not None else None
            ),
            "published_messages_per_second": (
                round(messages_published / publish_seconds, 2)
                if publish_seconds else None
            ),
            "delivered_fanout_events_per_second": (
                round(actual_deliveries / elapsed_seconds, 2)
                if elapsed_seconds else None
            ),
            "deliveries_per_client": distribution(per_client_counts),
            "publish_errors": publish_errors,
        },
        "sample_errors": unexpected[:20],
    }

    print(json.dumps(report, indent=2))
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nSaved report to {output_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://127.0.0.1:8000")
    parser.add_argument("--sessions", default="load_testing/sessions.json")
    parser.add_argument("--connections", type=int, default=50)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--ramp-up", type=float, default=5)
    parser.add_argument("--open-timeout", type=float, default=15)
    parser.add_argument(
        "--publishers", type=int, default=1,
        help="Number of connected clients publishing concurrently.",
    )
    parser.add_argument(
        "--messages", type=int, default=0,
        help="Messages sent by each publisher (not the aggregate total).",
    )
    parser.add_argument("--message-interval", type=float, default=0.1)
    parser.add_argument("--broadcast-timeout", type=float, default=15)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    if (
        args.connections < 1
        or args.duration < 0
        or args.ramp_up < 0
        or args.publishers < 1
        or args.messages < 0
        or args.message_interval < 0
        or args.broadcast_timeout < 0
    ):
        parser.error(
            "connections/publishers must be positive; duration, ramp-up, "
            "messages, intervals and timeouts must be non-negative"
        )
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
