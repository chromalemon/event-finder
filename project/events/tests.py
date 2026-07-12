from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from events.forms import BaseEventForm
from events.models import Event, Location, EventAttendee


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
				"start_time": (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
				"end_time": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
			}
		)

		self.assertFalse(missing_capacity_form.is_valid())
		self.assertIn("capacity", missing_capacity_form.errors)

		negative_capacity_form = BaseEventForm(
			data={
				"title": "Test event",
				"description": "Description",
				"start_time": (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
				"end_time": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
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
				"start_time": (timezone.now() + timezone.timedelta(days=-1)).strftime("%Y-%m-%dT%H:%M"),
				"end_time": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
				"capacity": 1,
			}
		)

		self.assertFalse(past_start_form.is_valid())
		self.assertIn("start_time", past_start_form.errors)

		bad_end_form = BaseEventForm(
			data={
				"title": "Test event",
				"description": "Desc",
				"start_time": (timezone.now() + timezone.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
				"end_time": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
				"capacity": 1,
			}
		)
		self.assertFalse(bad_end_form.is_valid())
		self.assertIn("end_time", bad_end_form.errors)	

	def test_view_events_sorts_descending_by_start_time(self):
		User = get_user_model()
		host = User.objects.create_user(username="host", email="host@example.com", password="pass12345")
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

		response = self.client.get(f"{reverse('events:view_events')}?sort=date_desc")
		self.assertContains(response, "Later event")
		self.assertContains(response, "Earlier event")
		self.assertLess(response.content.decode().find("Later event"), response.content.decode().find("Earlier event"))
	
	def test_waitlisted_user_promoted_upon_other_user_leaving(self):
		User = get_user_model()
		host = User.objects.create_user(username="host", email="host@example.com", password="pass12345")
		attendee1 = User.objects.create_user(username="attendee1", email="attendee1@example.com", password="pass12345")
		attendee2 = User.objects.create_user(username="attendee2", email="attendee2@example.com", password="pass12345")
		test_event = Event.objects.create(
			host=host,
			title="Test event",
			description="Desc",
			start_time=timezone.now() + timezone.timedelta(days=1),
			end_time=timezone.now() + timezone.timedelta(days=2),
			capacity=2
		)
		join1 = EventAttendee.objects.create(
			event=test_event,
			user=attendee1,
			status="going"
		)
		join2 = EventAttendee.objects.create(
			event=test_event,
			user=attendee2,
			status="waitlist"
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
		host = User.objects.create_user(username="host", email="host@example.com", password="pass12345")
		create_form1 = BaseEventForm(
			data={
				"title": "Test event 1",
				"description": "Desc",
				"start_time": (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
				"end_time": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
				"capacity": 1,
			}
		)
		create_form2 = BaseEventForm(
			data={
				"title": "Test event 2",
				"description": "Desc",
				"start_time": (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
				"end_time": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
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
				"start_time": (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
				"end_time": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
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
		host = User.objects.create(username="host", email="host@example.com", password="pass12345")
		form = BaseEventForm(
			data={
				"title": "Test event",
				"description": "Desc",
				"start_time": (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
				"end_time": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
				"capacity": 1,
			}
		)

		self.assertTrue(form.is_valid())
		event = form.save(commit=True, host=host)
		self.assertEqual(host.pk, event.host.pk)

	def test_edit_preserves_host(self):
		pass
	def test_changing_event_categories_preserves_categories_and_replaces_relations(self):
		pass