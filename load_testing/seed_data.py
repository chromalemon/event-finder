"""Create isolated Django users/event and export session cookies for WS tests.

Run inside the web container:
  python /app/load_testing/seed_data.py --users 100 --output /app/load_testing/sessions.json

This creates/updates only accounts with the configured username prefix.
"""
import argparse
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

PROJECT_DIR = Path("/app/project")
sys.path.insert(0, str(PROJECT_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "event_finder.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.sessions.backends.db import SessionStore  # noqa: E402
from django.utils import timezone  # noqa: E402
from events.models import Event, EventAttendee  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--prefix", default="loadtest")
    parser.add_argument("--event-id", type=int, default=None)
    parser.add_argument("--output", default="/app/load_testing/sessions.json")
    args = parser.parse_args()

    if args.users < 1:
        parser.error("--users must be positive")

    User = get_user_model()
    host, _ = User.objects.get_or_create(
        username=f"{args.prefix}_host",
        defaults={
            "email": f"{args.prefix}_host@example.invalid",
            "is_active": True,
        },
    )
    if not host.email:
        host.email = f"{args.prefix}_host@example.invalid"
        host.save(update_fields=["email"])

    if args.event_id is None:
        now = timezone.now()
        event = Event.objects.create(
            host=host,
            title=f"{args.prefix} WebSocket load test",
            description="Dedicated event created by the WebSocket load test.",
            start_time=now + timedelta(days=7),
            end_time=now + timedelta(days=7, hours=2),
            capacity=max(args.users + 1, 2),
        )
    else:
        event = Event.objects.get(pk=args.event_id)

    session_rows = []
    created = 0
    for index in range(args.users):
        username = f"{args.prefix}_{index:05d}"
        user, was_created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@example.invalid",
                "is_active": True,
            },
        )
        created += int(was_created)
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

        EventAttendee.objects.update_or_create(
            event=event,
            user=user,
            defaults={"status": "going"},
        )

        store = SessionStore()
        store["_auth_user_id"] = str(user.pk)
        store["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        store["_auth_user_hash"] = user.get_session_auth_hash()
        store.set_expiry(60 * 60 * 4)
        store.save()

        session_rows.append(
            {"username": username, "sessionid": store.session_key}
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "event_id": event.pk,
                "websocket_path": f"/ws/chat/event/{event.pk}/",
                "users": session_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Event ID: {event.pk}")
    print(f"Users requested: {args.users} (created: {created})")
    print(f"Session file: {output}")
    print("Keep this file private; it contains live authentication cookies.")


if __name__ == "__main__":
    main()
