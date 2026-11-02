import json
import logging
from time import perf_counter_ns

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

logger = logging.getLogger(__name__)
performance_logger = logging.getLogger("chat.performance")


class EventChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling chat messages.
    """

    async def connect(self):
        """
        Connect to the WebSocket and log timings for each setup stage.
        """
        connect_started_ns = perf_counter_ns()
        timings = {}
        outcome = "rejected"

        try:
            self.event_id = self.scope["url_route"]["kwargs"].get("event_id")
            if not self.event_id:
                await self.close()
                return

            user = self.scope["user"]
            if not user.is_authenticated:
                await self.close()
                return

            self.user_id = user.pk

            stage_started_ns = perf_counter_ns()
            try:
                allowed = await self._user_is_allowed(
                    self.user_id, self.event_id, timings
                )
            finally:
                timings["authorisation_ms"] = (
                    perf_counter_ns() - stage_started_ns
                ) / 1_000_000

            if not allowed:
                await self.close()
                return

            self.group_name = f"event_chat_{self.event_id}"

            stage_started_ns = perf_counter_ns()
            await self.channel_layer.group_add(
                self.group_name, self.channel_name
            )
            timings["group_add_ms"] = (
                perf_counter_ns() - stage_started_ns
            ) / 1_000_000

            stage_started_ns = perf_counter_ns()
            await self.accept()
            timings["accept_ms"] = (
                perf_counter_ns() - stage_started_ns
            ) / 1_000_000
            outcome = "accepted"

            try:
                stage_started_ns = perf_counter_ns()
                try:
                    recent = await self._get_recent_messages(
                        self.event_id, limit=50, timings=timings
                    )
                finally:
                    timings["history_query_and_serialisation_ms"] = (
                        perf_counter_ns() - stage_started_ns
                    ) / 1_000_000

                stage_started_ns = perf_counter_ns()
                try:
                    await self.send(
                        text_data=json.dumps(
                            {"type": "history", "messages": recent}
                        )
                    )
                finally:
                    timings["history_send_ms"] = (
                        perf_counter_ns() - stage_started_ns
                    ) / 1_000_000
            except Exception:
                logger.exception("Failed to load or send recent chat messages")
                timings["history_failed"] = True
        finally:
            timings["consumer_connect_total_ms"] = (
                perf_counter_ns() - connect_started_ns
            ) / 1_000_000
            timings["auth_middleware_ms"] = self.scope.get(
                "chat_auth_middleware_ms"
            )
            performance_logger.info(
                "chat_websocket_connect_timing %s",
                json.dumps(
                    {
                        "outcome": outcome,
                        "event_id": getattr(self, "event_id", None),
                        "timings": timings,
                    },
                    sort_keys=True,
                ),
            )

    async def disconnect(self, close_code):
        """
        Disconnect from the WebSocket and remove from the group.
        """
        if hasattr(self, "group_name"):
            try:
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )
            except Exception:
                logger.exception("Failed to disconnect from chat")

    async def receive(self, text_data=None, bytes_data=None):
        """
        Receive a message from the WebSocket.
        """
        if text_data is None:
            return
        data = json.loads(text_data)
        message = (data.get("message") or "").strip()
        if not message:
            return

        user = self.scope.get("user")
        saved_meta = None
        try:
            saved_meta = await self._save_message(
                self.event_id, self.user_id, message
            )
        except Exception:
            logger.exception("Failed to save message")

        payload = {
            "type": "chat.message",
            "message": message,
            "username": (
                getattr(user, "username", "anon")
                if (user and getattr(user, "is_authenticated", False))
                else "anon"
            ),
        }
        if saved_meta and isinstance(saved_meta, dict):
            payload.update(saved_meta)
        else:
            payload["timestamp"] = timezone.now().isoformat()

        await self.channel_layer.group_send(self.group_name, payload)

    async def chat_message(self, event):
        """
        Handle a chat message event.
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message",
                    "message": event.get("message"),
                    "username": event.get("username"),
                    "timestamp": event.get("timestamp"),
                    "id": event.get("id"),
                }
            )
        )

    @database_sync_to_async
    def _user_is_allowed(self, user_id, event_id, timings):
        """
        Check chat access and measure synchronous execution time.

        The caller's outer timer also includes time queued for a
        thread-sensitive database worker. This inner timer does not.
        """
        sync_started_ns = perf_counter_ns()
        try:
            from events.models import Event, EventAttendee

            try:
                event = Event.objects.get(pk=event_id)
            except Event.DoesNotExist:
                return False

            if event.host_id == user_id:
                return True

            return EventAttendee.objects.filter(
                event_id=event_id,
                user_id=user_id,
                status="going",
            ).exists()
        finally:
            timings["authorisation_sync_execution_ms"] = (
                perf_counter_ns() - sync_started_ns
            ) / 1_000_000

    @database_sync_to_async
    def _save_message(self, event_id, user_id, message_text):
        """
        Save a chat message to the database
        and return metadata about the saved message.
        """
        from .models import ChatMessage

        msg = ChatMessage.objects.create(
            event_id=event_id,
            user_id=user_id,
            content=message_text,
        )

        meta = {"id": getattr(msg, "pk", None)}
        val = msg.sent_at
        meta["timestamp"] = val.isoformat() if val else None

        return meta

    @database_sync_to_async
    def _get_recent_messages(self, event_id, limit=50, timings=None):
        """
        Retrieve recent chat messages and measure synchronous execution time.
        """
        sync_started_ns = perf_counter_ns()
        try:
            from .models import ChatMessage

            qs = (
                ChatMessage.objects.filter(event_id=event_id)
                .select_related("user")
                .order_by("-pk")[:limit]
            )
            out = []
            for message in reversed(list(qs)):
                user = getattr(message, "user", "anon")
                username = getattr(user, "username", str(user))
                val = message.sent_at

                out.append(
                    {
                        "username": username,
                        "message": message.content,
                        "timestamp": val.isoformat() if val else None,
                        "id": getattr(message, "pk", None),
                    }
                )
            return out
        finally:
            if timings is not None:
                timings["history_sync_execution_ms"] = (
                    perf_counter_ns() - sync_started_ns
                ) / 1_000_000
