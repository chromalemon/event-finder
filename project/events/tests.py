from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from events.forms import EventCreationForm
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
	def test_event_creation_form_rejects_missing_capacity(self):
		form = EventCreationForm(
			data={
				"title": "Test event",
				"description": "Description",
				"start_time": (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
				"end_time": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
			}
		)

		self.assertFalse(form.is_valid())
		self.assertIn("capacity", form.errors)

	def test_view_events_sorts_descending_by_start_time(self):
		User = get_user_model()
		host = User.objects.create_user(username="host", email="host@example.com", password="pass12345")
		old_location = Location.objects.create(
			formatted_address="Old Place",
			city="City",
			country="Country",
			postcode="00001",
			lat=1,
			long=1,
		)
		new_location = Location.objects.create(
			formatted_address="New Place",
			city="City",
			country="Country",
			postcode="00002",
			lat=2,
			long=2,
		)
		Event.objects.create(
			host=host,
			title="Earlier event",
			description="Desc",
			start_time=timezone.now() + timezone.timedelta(days=1),
			end_time=timezone.now() + timezone.timedelta(days=1, hours=1),
			location=old_location,
		)
		Event.objects.create(
			host=host,
			title="Later event",
			description="Desc",
			start_time=timezone.now() + timezone.timedelta(days=3),
			end_time=timezone.now() + timezone.timedelta(days=3, hours=1),
			location=new_location,
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
		self.client.login(username="attendee1", password="pass12345")
		url = reverse("events:leave_event", kwargs={"event_id": test_event.id})
		response = self.client.post(url)
		self.assertEqual(response.status_code, 302)
		join1.refresh_from_db()
		join2.refresh_from_db()
		self.assertEqual(join2.status, "going")
		self.assertEqual(join1.status, "not_going")
