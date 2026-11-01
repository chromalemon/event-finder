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
        return {"min_ms": None, "mean_ms": None, "p50_ms": None,
                "p95_ms": None, "p99_ms": None, "max_ms": None}
    return {
        "min_ms": round(min(values), 2),
        "mean_ms": round(statistics.fmean(values), 2),
        "p50_ms": round(percentile(values, 50), 2),
        "p95_ms": round(percentile(values, 95), 2),
        "p99_ms": round(percentile(values, 99), 2),
        "max_ms": round(max(values), 2),
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
    active = []
    unexpected = []
    delivery_ms = []
    ready = asyncio.Event()
    start_gate = asyncio.Event()
    expected_messages = args.messages
    received_counts = [0] * len(users)
    sent_at = {}
    receiver_tasks = []
    sockets = [None] * len(users)

    async def worker(index, user):
        cookie = f"sessionid={user['sessionid']}"
        await start_gate.wait()
        started = time.perf_counter()
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
                connect_ms.append((time.perf_counter() - started) * 1000)
                sockets[index] = ws
                # Consumer sends a history frame immediately after accepting.
                first = await asyncio.wait_for(ws.recv(), timeout=args.open_timeout)
                first_data = json.loads(first)
                if first_data.get("type") != "history":
                    outcomes["unexpected_initial_frame"] += 1
                outcomes["connected"] += 1
                active.append(index)
                ready.set()

                while True:
                    raw = await ws.recv()
                    payload = json.loads(raw)
                    if payload.get("type") == "message":
                        message = payload.get("message", "")
                        if message in sent_at:
                            received_counts[index] += 1
                            delivery_ms.append(
                                (time.perf_counter_ns() - sent_at[message]) / 1_000_000
                            )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            outcomes["timeout"] += 1
        except ConnectionClosed as exc:
            if not ready.is_set() or args.duration > 0:
                unexpected.append({"user": user["username"], "code": exc.code})
                outcomes["closed"] += 1
        except Exception as exc:
            outcomes["error"] += 1
            if len(unexpected) < 20:
                unexpected.append({"user": user["username"], "error": repr(exc)})

    tasks = [asyncio.create_task(worker(i, user)) for i, user in enumerate(users)]
    ramp_delay = args.ramp_up / max(args.connections, 1)
    start_gate.set()

    # Stagger task starts by delaying each worker's start through per-task gates
    # would add complexity; this ramp controls the overall connection launch.
    if args.ramp_up:
        await asyncio.sleep(args.ramp_up)
    else:
        await asyncio.sleep(0)

    deadline = time.perf_counter() + args.duration
    while time.perf_counter() < deadline:
        await asyncio.sleep(min(0.25, max(0, deadline - time.perf_counter())))

    # Optional broadcast phase: one client sends unique markers; every connected
    # client should receive each marker through the shared Redis group.
    if args.messages and active:
        publisher = sockets[active[0]]
        if publisher is not None:
            for sequence in range(args.messages):
                marker = f"loadtest:{uuid.uuid4().hex}:{sequence}"
                sent_at[marker] = time.perf_counter_ns()
                await publisher.send(json.dumps({"message": marker}))
                await asyncio.sleep(args.message_interval)
            expected = args.messages
            wait_until = time.perf_counter() + args.broadcast_timeout
            while time.perf_counter() < wait_until:
                if all(received_counts[i] >= expected for i in active):
                    break
                await asyncio.sleep(0.05)

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    expected_deliveries = len(active) * args.messages
    actual_deliveries = sum(received_counts[i] for i in active)
    report = {
        "target_connections": args.connections,
        "connected": outcomes["connected"],
        "failed_or_rejected": args.connections - outcomes["connected"],
        "unexpected_closures": outcomes["closed"],
        "timeouts": outcomes["timeout"],
        "other_errors": outcomes["error"],
        "active_at_end_of_idle_phase": len(active),
        "connection_latency": summary(connect_ms),
        "broadcast": {
            "messages_sent": args.messages,
            "expected_deliveries": expected_deliveries,
            "received_deliveries": actual_deliveries,
            "delivery_ratio": (
                round(actual_deliveries / expected_deliveries, 4)
                if expected_deliveries else None
            ),
            "delivery_latency": summary(delivery_ms),
        },
        "sample_errors": unexpected[:20],
    }
    print(json.dumps(report, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nSaved report to {args.output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://127.0.0.1:8000")
    parser.add_argument("--sessions", default="load_testing/sessions.json")
    parser.add_argument("--connections", type=int, default=50)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--ramp-up", type=float, default=5)
    parser.add_argument("--open-timeout", type=float, default=15)
    parser.add_argument("--messages", type=int, default=0,
                        help="Number of broadcasts from one connected client.")
    parser.add_argument("--message-interval", type=float, default=0.1)
    parser.add_argument("--broadcast-timeout", type=float, default=15)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    if args.connections < 1 or args.duration < 0 or args.ramp_up < 0:
        parser.error("connections must be positive; duration/ramp-up non-negative")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
