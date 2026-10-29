from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.forms import BaseEventForm
from events.models import Event, Location, EventAttendee, Category


class SmokeTests(TestCase):
    def test_home_page_returns_200(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)

    def test_dashboard_redirects_for_anonymous_users(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"{reverse('home')}?next={reverse('dashboard')}",
            fetch_redirect_response=False,
        )


class EventBehaviorTests(TestCase):
    def test_event_creation_form_rejects_invalid_capacity(self):
        missing_capacity_form = BaseEventForm(
            data={
                "title": "Test event",
                "description": "Description",
                "start_time": (
                    timezone.now() + timezone.timedelta(days=1)
                ).strftime("%Y-%m-%dT%H:%M"),
                "end_time": (
                    timezone.now() + timezone.timedelta(days=2)
                ).strftime("%Y-%m-%dT%H:%M"),
            }
        )

        self.assertFalse(missing_capacity_form.is_valid())
        self.assertIn("capacity", missing_capacity_form.errors)

        negative_capacity_form = BaseEventForm(
            data={
                "title": "Test event",
                "description": "Description",
                "start_time": (
                    timezone.now() + timezone.timedelta(days=1)
                ).strftime("%Y-%m-%dT%H:%M"),
                "end_time": (
                    timezone.now() + timezone.timedelta(days=2)
                ).strftime("%Y-%m-%dT%H:%M"),
                "capacity": -1,
            }
        )
        self.assertFalse(negative_capacity_form.is_valid())
        self.assertIn("capacity", negative_capacity_form.errors)

    def test_event_creation_form_rejects_invalid_start_end_times(self):
        past_start_form = BaseEventForm(
            data={
                "title": "Test event",
                "description": "Desc",
                "start_time": (
                    timezone.now() + timezone.timedelta(days=-1)
                ).strftime("%Y-%m-%dT%H:%M"),
                "end_time": (
                    timezone.now() + timezone.timedelta(days=2)
                ).strftime("%Y-%m-%dT%H:%M"),
                "capacity": 1,
            }
        )

        self.assertFalse(past_start_form.is_valid())
        self.assertIn("start_time", past_start_form.errors)

        bad_end_form = BaseEventForm(
            data={
                "title": "Test event",
                "description": "Desc",
                "start_time": (
                    timezone.now() + timezone.timedelta(days=3)
                ).strftime("%Y-%m-%dT%H:%M"),
                "end_time": (
                    timezone.now() + timezone.timedelta(days=2)
                ).strftime("%Y-%m-%dT%H:%M"),
                "capacity": 1,
            }
        )
        self.assertFalse(bad_end_form.is_valid())
        self.assertIn("end_time", bad_end_form.errors)

    def test_view_events_sorts_descending_by_start_time(self):
        User = get_user_model()
        host = User.objects.create_user(
            username="host", email="host@example.com", password="pass12345"
        )
        Event.objects.create(
            host=host,
            title="Earlier event",
            description="Desc",
            start_time=timezone.now() + timezone.timedelta(days=1),
            end_time=timezone.now() + timezone.timedelta(days=1, hours=1),
        )
        Event.objects.create(
            host=host,
            title="Later event",
            description="Desc",
            start_time=timezone.now() + timezone.timedelta(days=3),
            end_time=timezone.now() + timezone.timedelta(days=3, hours=1),
        )

        response = self.client.get(
            f"{reverse('events:view_events')}?sort=date_desc"
        )
        self.assertContains(response, "Later event")
        self.assertContains(response, "Earlier event")
        self.assertLess(
            response.content.decode().find("Later event"),
            response.content.decode().find("Earlier event"),
        )

    def test_waitlisted_user_promoted_upon_other_user_leaving(self):
        User = get_user_model()
        host = User.objects.create_user(
            username="host", email="host@example.com", password="pass12345"
        )
        attendee1 = User.objects.create_user(
            username="attendee1",
            email="attendee1@example.com",
            password="pass12345",
        )
        attendee2 = User.objects.create_user(
            username="attendee2",
            email="attendee2@example.com",
            password="pass12345",
        )
        test_event = Event.objects.create(
            host=host,
            title="Test event",
            description="Desc",
            start_time=timezone.now() + timezone.timedelta(days=1),
            end_time=timezone.now() + timezone.timedelta(days=2),
            capacity=2,
        )
        join1 = EventAttendee.objects.create(
            event=test_event, user=attendee1, status="going"
        )
        join2 = EventAttendee.objects.create(
            event=test_event, user=attendee2, status="waitlist"
        )
        self.client.force_login(attendee1)
        url = reverse("events:leave_event", kwargs={"event_id": test_event.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        join1.refresh_from_db()
        join2.refresh_from_db()
        self.assertEqual(join2.status, "going")
        self.assertEqual(join1.status, "not_going")

    def test_event_creation_reuses_or_creates_new_location(self):
        User = get_user_model()
        host = User.objects.create_user(
            username="host", email="host@example.com", password="pass12345"
        )
        create_form1 = BaseEventForm(
            data={
                "title": "Test event 1",
                "description": "Desc",
                "start_time": (
                    timezone.now() + timezone.timedelta(days=1)
                ).strftime("%Y-%m-%dT%H:%M"),
                "end_time": (
                    timezone.now() + timezone.timedelta(days=2)
                ).strftime("%Y-%m-%dT%H:%M"),
                "capacity": 1,
            }
        )
        create_form2 = BaseEventForm(
            data={
                "title": "Test event 2",
                "description": "Desc",
                "start_time": (
                    timezone.now() + timezone.timedelta(days=1)
                ).strftime("%Y-%m-%dT%H:%M"),
                "end_time": (
                    timezone.now() + timezone.timedelta(days=2)
                ).strftime("%Y-%m-%dT%H:%M"),
                "capacity": 1,
            }
        )

        self.assertTrue(create_form1.is_valid() and create_form2.is_valid())
        event1 = create_form1.save(commit=True, host=host)
        event2 = create_form2.save(commit=True, host=host)
        self.assertEqual(event1.location.pk, event2.location.pk)

        loc = Location.objects.create(
            formatted_address="Test location",
            city="City",
            country="Country",
            postcode="00001",
            lat=1,
            long=1,
        )

        create_form3 = BaseEventForm(
            data={
                "title": "Test event 3",
                "description": "Desc",
                "start_time": (
                    timezone.now() + timezone.timedelta(days=1)
                ).strftime("%Y-%m-%dT%H:%M"),
                "end_time": (
                    timezone.now() + timezone.timedelta(days=2)
                ).strftime("%Y-%m-%dT%H:%M"),
                "capacity": 1,
                "formatted_address": "Test location",
                "lat": 1,
                "long": 1,
            }
        )

        self.assertTrue(create_form3.is_valid())
        event3 = create_form3.save(commit=True, host=host)
        self.assertEqual(event3.location.pk, loc.pk)

    def test_event_creation_assigns_host(self):
        User = get_user_model()
        host = User.objects.create(
            username="host", email="host@example.com", password="pass12345"
        )
        form = BaseEventForm(
            data={
                "title": "Test event",
                "description": "Desc",
                "start_time": (
                    timezone.now() + timezone.timedelta(days=1)
                ).strftime("%Y-%m-%dT%H:%M"),
                "end_time": (
                    timezone.now() + timezone.timedelta(days=2)
                ).strftime("%Y-%m-%dT%H:%M"),
                "capacity": 1,
            }
        )

        self.assertTrue(form.is_valid())
        event = form.save(commit=True, host=host)
        self.assertEqual(host.pk, event.host.pk)

    def test_edit_preserves_host(self):
        pass

    def test_changing_event_categories_replaces_relations(
        self,
    ):
        pass


class EventListingFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.host = User.objects.create_user(
            username="listing_host",
            email="listing_host@example.com",
            password="pass12345",
        )

        cls.london = Location.objects.create(
            formatted_address="10 Example Road, London",
            city="London",
            country="United Kingdom",
            postcode="SW1A 1AA",
            lat=51.5072,
            long=-0.1276,
        )

        cls.manchester = Location.objects.create(
            formatted_address="20 Example Street, Manchester",
            city="Manchester",
            country="United Kingdom",
            postcode="M1 1AA",
            lat=53.4808,
            long=-2.2426,
        )

        cls.technology = Category.objects.create(name="Technology")
        cls.music = Category.objects.create(name="Music")

        cls.london_event = cls.create_event(
            "Python Meetup",
            cls.london,
            days_ahead=2,
        )
        cls.manchester_event = cls.create_event(
            "Live Music Night",
            cls.manchester,
            days_ahead=3,
        )

        cls.london_event.event_categories.create(cat=cls.technology)
        cls.manchester_event.event_categories.create(cat=cls.music)

    @classmethod
    def create_event(cls, title, location, days_ahead):
        start = timezone.now() + timezone.timedelta(days=days_ahead)

        return Event.objects.create(
            host=cls.host,
            title=title,
            description="Test event description",
            location=location,
            start_time=start,
            end_time=start + timezone.timedelta(hours=2),
            capacity=10,
        )

    def get_event_ids(self, response):
        return {event.pk for event in response.context["events"].object_list}

    def test_search_filters_by_event_title(self):
        response = self.client.get(
            reverse("events:view_events"),
            {"q": "Python"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.get_event_ids(response),
            {self.london_event.pk},
        )

    def test_city_filter_returns_matching_events(self):
        response = self.client.get(
            reverse("events:view_events"),
            {"city": "Manchester"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.get_event_ids(response),
            {self.manchester_event.pk},
        )

    def test_country_filter_returns_matching_events(self):
        response = self.client.get(
            reverse("events:view_events"),
            {"country": "United Kingdom"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.get_event_ids(response),
            {self.london_event.pk, self.manchester_event.pk},
        )

    def test_category_filter_returns_matching_events(self):
        response = self.client.get(
            reverse("events:view_events"),
            {"category": "Technology"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.get_event_ids(response),
            {self.london_event.pk},
        )

    def test_event_listing_paginates_after_ten_events(self):
        for index in range(11):
            self.create_event(
                f"Pagination Event {index:02d}",
                self.london,
                days_ahead=index + 5,
            )

        response_page_1 = self.client.get(
            reverse("events:view_events"),
            {"page": 1},
        )
        response_page_2 = self.client.get(
            reverse("events:view_events"),
            {"page": 2},
        )

        self.assertEqual(response_page_1.status_code, 200)
        self.assertEqual(response_page_2.status_code, 200)

        page_1 = response_page_1.context["events"]
        page_2 = response_page_2.context["events"]

        self.assertEqual(page_1.paginator.count, 13)
        self.assertEqual(len(page_1.object_list), 10)
        self.assertEqual(len(page_2.object_list), 3)

        page_1_ids = {event.pk for event in page_1.object_list}
        page_2_ids = {event.pk for event in page_2.object_list}

        self.assertTrue(page_1_ids.isdisjoint(page_2_ids))


class EventAttendanceViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.host = User.objects.create_user(
            username="attendance_host",
            email="attendance_host@example.com",
            password="pass12345",
        )
        cls.attendee = User.objects.create_user(
            username="attendance_user",
            email="attendance_user@example.com",
            password="pass12345",
        )
        cls.other_user = User.objects.create_user(
            username="attendance_other",
            email="attendance_other@example.com",
            password="pass12345",
        )

        cls.event = Event.objects.create(
            host=cls.host,
            title="Attendance test event",
            description="Testing attendance",
            start_time=timezone.now() + timezone.timedelta(days=2),
            end_time=timezone.now() + timezone.timedelta(days=2, hours=2),
            capacity=1,
        )

    def test_join_event_creates_going_attendance(self):
        self.client.force_login(self.attendee)

        response = self.client.post(
            reverse(
                "events:join_event",
                kwargs={"event_id": self.event.id},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse(
                "events:view_event",
                kwargs={"event_id": self.event.id},
            ),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            EventAttendee.objects.filter(
                event=self.event,
                user=self.attendee,
                status="going",
            ).exists()
        )

    def test_join_full_event_adds_user_to_waitlist(self):
        EventAttendee.objects.create(
            event=self.event,
            user=self.other_user,
            status="going",
        )
        self.client.force_login(self.attendee)

        response = self.client.post(
            reverse(
                "events:join_event",
                kwargs={"event_id": self.event.id},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            EventAttendee.objects.filter(
                event=self.event,
                user=self.attendee,
                status="waitlist",
            ).exists()
        )

    def test_already_attending_user_is_not_duplicated(self):
        existing = EventAttendee.objects.create(
            event=self.event,
            user=self.attendee,
            status="going",
        )
        self.client.force_login(self.attendee)

        response = self.client.post(
            reverse(
                "events:join_event",
                kwargs={"event_id": self.event.id},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            EventAttendee.objects.filter(
                event=self.event,
                user=self.attendee,
            ).count(),
            1,
        )
        existing.refresh_from_db()
        self.assertEqual(existing.status, "going")

    def test_banned_user_cannot_join_event(self):
        EventAttendee.objects.create(
            event=self.event,
            user=self.attendee,
            status="banned",
        )
        self.client.force_login(self.attendee)

        self.client.post(
            reverse(
                "events:join_event",
                kwargs={"event_id": self.event.id},
            )
        )

        attendee = EventAttendee.objects.get(
            event=self.event,
            user=self.attendee,
        )
        self.assertEqual(attendee.status, "banned")

    def test_leave_event_without_existing_record_creates_not_going(self):
        self.client.force_login(self.attendee)

        response = self.client.post(
            reverse(
                "events:leave_event",
                kwargs={"event_id": self.event.id},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            EventAttendee.objects.filter(
                event=self.event,
                user=self.attendee,
                status="not_going",
            ).exists()
        )

    def test_non_host_cannot_manage_attendee_status(self):
        attendee_record = EventAttendee.objects.create(
            event=self.event,
            user=self.other_user,
            status="waitlist",
        )
        self.client.force_login(self.attendee)

        response = self.client.post(
            reverse(
                "events:change_attendee_status",
                kwargs={"event_id": self.event.id},
            ),
            {
                "attendee_id": attendee_record.id,
                "status": "going",
            },
        )

        self.assertEqual(response.status_code, 403)
        attendee_record.refresh_from_db()
        self.assertEqual(attendee_record.status, "waitlist")

    def test_host_cannot_promote_attendee_when_event_is_full(self):
        attendee_record = EventAttendee.objects.create(
            event=self.event,
            user=self.other_user,
            status="waitlist",
        )
        EventAttendee.objects.create(
            event=self.event,
            user=self.attendee,
            status="going",
        )
        self.client.force_login(self.host)

        response = self.client.post(
            reverse(
                "events:change_attendee_status",
                kwargs={"event_id": self.event.id},
            ),
            {
                "attendee_id": attendee_record.id,
                "status": "going",
            },
        )

        self.assertEqual(response.status_code, 302)
        attendee_record.refresh_from_db()
        self.assertEqual(attendee_record.status, "waitlist")

    def test_host_can_remove_attendee(self):
        attendee_record = EventAttendee.objects.create(
            event=self.event,
            user=self.other_user,
            status="waitlist",
        )
        self.client.force_login(self.host)

        response = self.client.post(
            reverse(
                "events:change_attendee_status",
                kwargs={"event_id": self.event.id},
            ),
            {
                "attendee_id": attendee_record.id,
                "action": "remove",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            EventAttendee.objects.filter(pk=attendee_record.id).exists()
        )

    def test_invalid_attendee_status_is_rejected(self):
        attendee_record = EventAttendee.objects.create(
            event=self.event,
            user=self.other_user,
            status="waitlist",
        )
        self.client.force_login(self.host)

        response = self.client.post(
            reverse(
                "events:change_attendee_status",
                kwargs={"event_id": self.event.id},
            ),
            {
                "attendee_id": attendee_record.id,
                "status": "invalid_status",
            },
        )

        self.assertEqual(response.status_code, 302)
        attendee_record.refresh_from_db()
        self.assertEqual(attendee_record.status, "waitlist")

    def test_missing_attendee_id_is_handled(self):
        self.client.force_login(self.host)

        response = self.client.post(
            reverse(
                "events:change_attendee_status",
                kwargs={"event_id": self.event.id},
            ),
            {"status": "going"},
        )

        self.assertEqual(response.status_code, 302)
