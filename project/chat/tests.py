from django.test import TestCase
from django.contrib.auth import get_user_model
from events.models import Event, EventAttendee
from django.utils import timezone
from django.urls import reverse


class ChatTests(TestCase):
    def test_chat_page_requires_login_as_host_or_attendee(self):
        # need to split this up
        User = get_user_model()
        host = User.objects.create_user(
            username="host", email="host@example.com", password="pass12345"
        )
        event = Event.objects.create(
            host=host,
            title="Test event",
            description="Desc",
            start_time=timezone.now() + timezone.timedelta(days=1),
            end_time=timezone.now() + timezone.timedelta(days=2),
            capacity=5,
        )

        url = reverse("chat:room", kwargs={"event_id": event.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"/?next=/chat/room/{event.id}/",
            fetch_redirect_response=False,
        )

        self.client.force_login(host)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        random_user = User.objects.create_user(
            username="random_user",
            email="random@example.com",
            password="pass12345",
        )
        self.client.login(username="random_user", password="pass12345")
        response = self.client.get(url)
        self.assertContains(response, "Access Restricted")

        EventAttendee.objects.create(
            event=event, user=random_user, status="going"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
