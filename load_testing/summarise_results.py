"""Turn saved WebSocket stress-test JSON files into a benchmark report and CV evidence."""
import argparse
import json
from pathlib import Path


def load_result(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    # Current concurrent-publisher schema.
    if "connections" in data:
        connections = data["connections"]
        broadcast = data.get("broadcast", {})
        test = data.get("test", {})
        return {
            "file": path.name,
            "target": test.get("target_connections"),
            "connected": connections.get("connected", 0),
            "active": connections.get("active_at_end_of_idle_phase", 0),
            "failed": connections.get("failed_or_rejected", 0),
            "closures": connections.get("unexpected_closures", 0),
            "timeouts": connections.get("timeouts", 0),
            "connection_p95": connections.get("connection_latency", {}).get("p95_ms"),
            "publishers": test.get("publishers_active", 1),
            "messages": broadcast.get("messages_published", 0),
            "expected": broadcast.get("expected_deliveries", 0),
            "received": broadcast.get("unique_received_deliveries", 0),
            "missing": broadcast.get("missing_deliveries", 0),
            "duplicates": broadcast.get("duplicate_deliveries", 0),
            "ratio": broadcast.get("delivery_ratio"),
            "delivery_p95": broadcast.get("delivery_latency", {}).get("p95_ms"),
            "fanout_rate": broadcast.get("delivered_fanout_events_per_second"),
        }

    # Backward compatibility with the original single-publisher result schema.
    broadcast = data.get("broadcast", {})
    return {
        "file": path.name,
        "target": data.get("target_connections"),
        "connected": data.get("connected", 0),
        "active": data.get("active_at_end_of_idle_phase", 0),
        "failed": data.get("failed_or_rejected", 0),
        "closures": data.get("unexpected_closures", 0),
        "timeouts": data.get("timeouts", 0),
        "connection_p95": data.get("connection_latency", {}).get("p95_ms"),
        "publishers": 1,
        "messages": broadcast.get("messages_sent", 0),
        "expected": broadcast.get("expected_deliveries", 0),
        "received": broadcast.get("received_deliveries", 0),
        "missing": max(
            0,
            broadcast.get("expected_deliveries", 0)
            - broadcast.get("received_deliveries", 0),
        ),
        "duplicates": None,
        "ratio": broadcast.get("delivery_ratio"),
        "delivery_p95": broadcast.get("delivery_latency", {}).get("p95_ms"),
        "fanout_rate": None,
    }


def fmt(value, suffix=""):
    return "—" if value is None else f"{value}{suffix}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", help="Saved stress-test JSON result files")
    parser.add_argument(
        "--output", default="load_testing/benchmark-report.md",
        help="Markdown report path (default: load_testing/benchmark-report.md)",
    )
    args = parser.parse_args()

    rows = [load_result(Path(name)) for name in args.results]
    max_stable = max(
        (row for row in rows if row["connected"] == row["target"]
         and row["active"] == row["target"] and row["failed"] == 0
         and row["closures"] == 0 and row["timeouts"] == 0),
        key=lambda row: row["connected"],
        default=None,
    )
    full_broadcasts = [
        row for row in rows
        if row["expected"] and row["ratio"] is not None
        and row["ratio"] >= 1.0 and row["missing"] == 0
        and row["duplicates"] in (None, 0)
    ]
    best_broadcast = max(
        full_broadcasts,
        key=lambda row: row["expected"],
        default=None,
    )

    lines = [
        "# WebSocket load-test benchmark report",
        "",
        "Generated from the supplied JSON result files. These are measurements "
        "from the tested environment and workload, not a production capacity guarantee.",
        "",
        "| Result file | Connected / target | Active | Failures | Publishers | Messages published | Expected deliveries | Received | Delivery ratio | Delivery p95 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        ratio = fmt(
            round(row["ratio"] * 100, 2) if row["ratio"] is not None else None,
            "%",
        )
        lines.append(
            f"| {row['file']} | {row['connected']} / {fmt(row['target'])} "
            f"| {row['active']} | {row['failed']} | {row['publishers']} "
            f"| {row['messages']} | {row['expected']} | {row['received']} "
            f"| {ratio} | {fmt(row['delivery_p95'], ' ms')} |"
        )

    lines.extend(["", "## Highest stable connection result", ""])
    if max_stable:
        lines.append(
            f"- **{max_stable['connected']} concurrent connections** remained "
            f"active at the end of the test, with zero failed/rejected connections, "
            f"unexpected closures or timeouts."
        )
        lines.append(
            f"- Connection-establishment p95 (through initial history frame): "
            f"{fmt(max_stable['connection_p95'], ' ms')}."
        )
    else:
        lines.append("No result met the strict stable-connection criteria.")

    lines.extend(["", "## Highest fully delivered broadcast result", ""])
    if best_broadcast:
        lines.append(
            f"- **{best_broadcast['expected']:,} / {best_broadcast['expected']:,} "
            f"expected client-message deliveries** were received across "
            f"{best_broadcast['active']} clients using "
            f"{best_broadcast['publishers']} publisher(s)."
        )
        lines.append(
            f"- Delivery p95: {fmt(best_broadcast['delivery_p95'], ' ms')}."
        )
    else:
        lines.append(
            "No broadcast result met the full-delivery criteria. Do not claim "
            "100% delivery in a CV bullet."
        )

    lines.extend(["", "## CV-ready evidence", ""])
    if max_stable and best_broadcast:
        lines.append(
            f"- Built and load-tested an authenticated Django Channels WebSocket "
            f"chat service, sustaining {max_stable['connected']} concurrent "
            f"connections and delivering {best_broadcast['expected']:,} / "
            f"{best_broadcast['expected']:,} expected broadcast deliveries across "
            f"{best_broadcast['active']} clients "
            f"({best_broadcast['publishers']} concurrent publisher(s); delivery "
            f"p95 {fmt(best_broadcast['delivery_p95'], ' ms')}) using Redis."
        )
        lines.append("")
        lines.append(
            "Use this bullet only with the workload and environment clearly "
            "understood; retain the JSON files as supporting evidence."
        )
    else:
        lines.append(
            "Collect at least one clean connection test and one fully delivered "
            "broadcast test before using a quantified performance claim."
        )

    lines.extend([
        "",
        "## Measurement notes",
        "",
        "- Connection latency runs from the client connection attempt through "
        "receipt of the initial history frame.",
        "- Delivery latency is measured by the load-generator process from just "
        "before the publisher sends a marker until a recipient receives it; it "
        "includes client scheduling, server processing and fan-out.",
        "- A client-message delivery is one unique (recipient, message) pair. "
        "Duplicate deliveries are excluded from the received count and reported "
        "separately by the concurrent-publisher harness.",
        "- The load generator and application may share a host. Results therefore "
        "describe this local test setup, not independently verified server capacity.",
        "",
    ])

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote benchmark report to {output}")


if __name__ == "__main__":
    main()
