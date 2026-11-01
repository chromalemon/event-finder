"""Verify that every concurrently published load-test chat message reached PostgreSQL.

Run inside the web container after websocket_stress.py has completed:
  python /app/load_testing/verify_chat_persistence.py \
      --results /app/load_testing/concurrent-500x10.json
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path("/app/project")
sys.path.insert(0, str(PROJECT_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "event_finder.settings")

import django  # noqa: E402

django.setup()

from chat.models import ChatMessage  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, help="Stress-test JSON report")
    args = parser.parse_args()

    path = Path(args.results)
    report = json.loads(path.read_text(encoding="utf-8"))
    markers = report.get("broadcast", {}).get("published_message_markers", [])
    event_id = report.get("event_id")
    if not event_id:
        parser.error("Result file has no event_id; use a report from the updated harness.")
    if not markers:
        parser.error("Result file contains no published message markers.")

    rows = ChatMessage.objects.filter(
        event_id=event_id,
        content__in=markers,
    ).values_list("content", flat=True)
    counts = Counter(rows)
    missing = [marker for marker in markers if counts[marker] == 0]
    duplicates = {
        marker: count for marker, count in counts.items() if count > 1
    }
    persisted = sum(1 for marker in markers if counts[marker] > 0)

    verification = {
        "event_id": event_id,
        "messages_published": len(markers),
        "messages_persisted": persisted,
        "missing_messages": len(missing),
        "duplicate_database_rows": sum(count - 1 for count in duplicates.values()),
        "persistence_ratio": round(persisted / len(markers), 6),
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "sample_missing_markers": missing[:20],
        "sample_duplicate_markers": list(duplicates)[:20],
    }
    report["persistence"] = verification
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verification, indent=2))
    print(f"Updated benchmark report: {path}")


if __name__ == "__main__":
    main()
