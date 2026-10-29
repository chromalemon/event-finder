from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from events.models import Event, EventAttendee
from asgiref.sync import async_to_sync
from chat.consumers import EventChatConsumer
from chat.models import ChatMessage


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


class ChatConsumerDatabaseTests(TransactionTestCase):
    def setUp(self):
        User = get_user_model()

        self.host = User.objects.create_user(
            username="chat_host",
            email="chat_host@example.com",
            password="pass12345",
        )

        self.attendee = User.objects.create_user(
            username="chat_attendee",
            email="chat_attendee@example.com",
            password="pass12345",
        )

        self.other_user = User.objects.create_user(
            username="chat_other",
            email="chat_other@example.com",
            password="pass12345",
        )

        self.event = Event.objects.create(
            host=self.host,
            title="Chat test event",
            description="Testing chat",
            start_time=timezone.now() + timezone.timedelta(days=1),
            end_time=timezone.now() + timezone.timedelta(days=2),
            capacity=5,
        )

        self.consumer = EventChatConsumer()

    def test_host_is_allowed(self):
        allowed = async_to_sync(self.consumer._user_is_allowed)(
            self.host, self.event.id
        )

        self.assertTrue(allowed)

    def test_attendee_with_going_status_is_allowed(self):
        EventAttendee.objects.create(
            event=self.event,
            user=self.attendee,
            status="going",
        )

        allowed = async_to_sync(self.consumer._user_is_allowed)(
            self.attendee, self.event.id
        )

        self.assertTrue(allowed)

    def test_other_user_is_not_allowed(self):
        allowed = async_to_sync(self.consumer._user_is_allowed)(
            self.other_user, self.event.id
        )

        self.assertFalse(allowed)

    def test_missing_event_is_not_allowed(self):
        allowed = async_to_sync(self.consumer._user_is_allowed)(
            self.host, 999999
        )

        self.assertFalse(allowed)

    def test_authenticated_message_is_saved(self):
        metadata = async_to_sync(self.consumer._save_message)(
            self.event.id,
            self.attendee,
            "Hello everyone",
        )

        self.assertIsNotNone(metadata)
        self.assertIsNotNone(metadata["id"])

        message = ChatMessage.objects.get(pk=metadata["id"])
        self.assertEqual(message.event_id, self.event.id)
        self.assertEqual(message.user_id, self.attendee.id)
        self.assertEqual(message.content, "Hello everyone")

    def test_unauthenticated_message_is_not_saved(self):
        from django.contrib.auth.models import AnonymousUser

        metadata = async_to_sync(self.consumer._save_message)(
            self.event.id,
            AnonymousUser(),
            "Anonymous message",
        )

        self.assertIsNone(metadata)
        self.assertEqual(
            ChatMessage.objects.filter(event=self.event).count(), 0
        )

    def test_recent_messages_are_returned_oldest_first(self):
        async_to_sync(self.consumer._save_message)(
            self.event.id, self.attendee, "First message"
        )
        async_to_sync(self.consumer._save_message)(
            self.event.id, self.attendee, "Second message"
        )

        messages = async_to_sync(self.consumer._get_recent_messages)(
            self.event.id
        )

        self.assertEqual(
            [message["message"] for message in messages],
            ["First message", "Second message"],
        )

    def test_recent_messages_respect_limit(self):
        for index in range(3):
            async_to_sync(self.consumer._save_message)(
                self.event.id,
                self.attendee,
                f"Message {index}",
            )

        messages = async_to_sync(self.consumer._get_recent_messages)(
            self.event.id, limit=2
        )

        self.assertEqual(
            [message["message"] for message in messages],
            ["Message 1", "Message 2"],
        )
