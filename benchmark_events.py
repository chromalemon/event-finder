import random
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from events.models import Category, Event, EventCategory, Location
from users.models import CustomUser

PREFIX = "BENCHMARK_ONLY_"
EVENT_COUNT = 1000
RNG = random.Random(42)

CITIES = [
    ("London", "United Kingdom", 51.5072, -0.1276),
    ("Manchester", "United Kingdom", 53.4808, -2.2426),
    ("Bristol", "United Kingdom", 51.4545, -2.5879),
    ("Edinburgh", "United Kingdom", 55.9533, -3.1883),
    ("Leeds", "United Kingdom", 53.8008, -1.5491),
]

CATEGORY_NAMES = [
    PREFIX + "Technology",
    PREFIX + "Music",
    PREFIX + "Sports",
    PREFIX + "Arts",
    PREFIX + "Networking",
]

def seed():
    if Event.objects.filter(title__startswith=PREFIX).exists():
        raise RuntimeError(
            "Benchmark events already exist. Clean up the previous "
            "benchmark dataset before seeding again."
        )

    now = timezone.now()

    with transaction.atomic():
        host, _ = CustomUser.objects.get_or_create(
            username=PREFIX + "host",
            defaults={
                "email": "benchmark-host@example.invalid",
                "first_name": "Benchmark",
                "last_name": "Host",
                "is_active": True,
            },
        )

        categories = []
        for name in CATEGORY_NAMES:
            category, _ = Category.objects.get_or_create(name=name)
            categories.append(category)

        locations = []
        for city, country, lat, lon in CITIES:
            location = Location.objects.create(
                formatted_address=f"{PREFIX}{city}, {country}",
                city=city,
                country=country,
                postcode="BENCH",
                lat=lat,
                long=lon,
            )
            locations.append(location)

        events = []
        for i in range(EVENT_COUNT):
            city_index = i % len(locations)
            start = now + timedelta(
                days=RNG.randint(-30, 180),
                hours=RNG.randint(0, 23),
            )
            events.append(
                Event(
                    host=host,
                    title=f"{PREFIX} Event {i:04d} "
                          f"{CITIES[city_index][0]}",
                    description=(
                        f"Synthetic benchmark event {i}. "
                        "Generated only for local performance testing."
                    ),
                    start_time=start,
                    end_time=start + timedelta(hours=2),
                    location=locations[city_index],
                    capacity=RNG.randint(10, 500),
                )
            )

        Event.objects.bulk_create(events, batch_size=250)

        # Attach one category to every generated event.
        generated_events = list(
            Event.objects.filter(title__startswith=PREFIX).order_by("id")
        )
        EventCategory.objects.bulk_create(
            [
                EventCategory(
                    event=event,
                    cat=categories[i % len(categories)],
                )
                for i, event in enumerate(generated_events)
            ],
            batch_size=250,
        )

    print(f"Created {len(generated_events)} benchmark events.")
    print(f"Created {len(locations)} benchmark locations.")
    print(f"Created {len(categories)} benchmark categories.")
    print(f"Benchmark prefix: {PREFIX}")

def cleanup():
    with transaction.atomic():
        events = Event.objects.filter(title__startswith=PREFIX)
        event_count = events.count()
        events.delete()

        locations = Location.objects.filter(
            formatted_address__startswith=PREFIX
        )
        location_count = locations.count()
        locations.delete()

        categories = Category.objects.filter(name__startswith=PREFIX)
        category_count = categories.count()
        categories.delete()

        hosts = CustomUser.objects.filter(username=PREFIX + "host")
        host_count = hosts.count()
        hosts.delete()

    print(f"Deleted {event_count} benchmark events.")
    print(f"Deleted {location_count} benchmark locations.")
    print(f"Deleted {category_count} benchmark categories.")
    print(f"Deleted {host_count} benchmark hosts.")

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2 or sys.argv[1] not in {"seed", "cleanup"}:
        raise SystemExit(
            "Usage: python manage.py shell < benchmark_events.py "
            "(seed or cleanup is selected by editing the final call)"
        )

    if sys.argv[1] == "seed":
        seed()
    else:
        cleanup()
