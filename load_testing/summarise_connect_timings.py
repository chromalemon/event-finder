"""Summarise structured WebSocket connection timing records from web logs."""

import argparse
import json
import math
import statistics
from pathlib import Path

MARKER = "chat_websocket_connect_timing "
TIMING_FIELDS = (
    "auth_middleware_ms",
    "authorisation_ms",
    "group_add_ms",
    "accept_ms",
    "history_query_and_serialisation_ms",
    "history_send_ms",
    "consumer_connect_total_ms",
    "authorisation_sync_execution_ms",
    "history_sync_execution_ms",
)

# (derived name, outer await timing, inner synchronous execution timing).
# outer - inner approximates time queued for the thread-sensitive database
# worker, plus small wrapper and scheduling overheads.
WAIT_PAIRS = (
    ("authorisation_worker_wait_ms", "authorisation_ms",
     "authorisation_sync_execution_ms"),
    ("history_worker_wait_ms", "history_query_and_serialisation_ms",
     "history_sync_execution_ms"),
)


def is_number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def percentile(values, p):
    ordered = sorted(values)
    index = max(0, min(math.ceil(p / 100 * len(ordered)) - 1, len(ordered) - 1))
    return ordered[index]


def summarise(values):
    if not values:
        return None
    return {
        "count": len(values),
        "min_ms": round(min(values), 2),
        "mean_ms": round(statistics.fmean(values), 2),
        "p50_ms": round(percentile(values, 50), 2),
        "p95_ms": round(percentile(values, 95), 2),
        "p99_ms": round(percentile(values, 99), 2),
        "max_ms": round(max(values), 2),
    }


def load_records(path):
    records = []
    malformed = 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        marker_index = line.find(MARKER)
        if marker_index == -1:
            continue
        try:
            records.append(json.loads(line[marker_index + len(MARKER):]))
        except json.JSONDecodeError:
            malformed += 1
    return records, malformed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_file", help="File captured from docker compose logs")
    parser.add_argument("--output", help="Optional path for a JSON summary")
    args = parser.parse_args()

    records, malformed = load_records(args.log_file)
    outcomes = {}
    for record in records:
        outcome = record.get("outcome", "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    summary = {
        "records": len(records),
        "malformed_records": malformed,
        "outcomes": outcomes,
        "timings": {},
    }

    for field in TIMING_FIELDS:
        values = [
            record.get("timings", {}).get(field)
            for record in records
        ]
        values = [value for value in values if is_number(value)]
        summary["timings"][field] = summarise(values)

    # Per-record differences, so each wait is paired with its own execution.
    summary["derived"] = {}
    for name, outer_field, inner_field in WAIT_PAIRS:
        waits = []
        inner_values = []
        for record in records:
            timings = record.get("timings", {})
            outer = timings.get(outer_field)
            inner = timings.get(inner_field)
            if is_number(outer) and is_number(inner):
                waits.append(outer - inner)
                inner_values.append(inner)
        summary["derived"][name] = summarise(waits)
        if waits:
            total_outer = sum(waits) + sum(inner_values)
            summary["derived"][name]["wait_share_of_outer"] = round(
                sum(waits) / total_outer, 3
            ) if total_outer else None

    # If one thread runs all synchronous ORM work, the summed execution time
    # is a lower bound on how long the last connection had to wait.
    summary["derived"]["summed_sync_execution_ms"] = round(
        sum(
            record.get("timings", {}).get(field, 0)
            for record in records
            for field in (
                "authorisation_sync_execution_ms",
                "history_sync_execution_ms",
            )
            if is_number(record.get("timings", {}).get(field))
        ),
        2,
    )

    output = json.dumps(summary, indent=2)
    print(output)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
        print(f"\nSaved summary to {args.output}")


if __name__ == "__main__":
    main()
