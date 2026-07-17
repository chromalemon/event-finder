from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
from django.utils import timezone


class EventChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling chat messages.
    """

    async def connect(self):
        """
        Connect to the WebSocket.
        """
        self.event_id = self.scope["url_route"]["kwargs"].get("event_id")
        if not self.event_id:
            await self.close()
            return

        try:
            ok = await self._user_is_allowed(
                self.scope.get("user"), self.event_id
            )
        except Exception:
            await self.close()
            return

        if not ok:
            await self.close()
            return

        self.group_name = f"event_chat_{self.event_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # send recent messages
        try:
            recent = await self._get_recent_messages(self.event_id, limit=50)
            await self.send(
                text_data=json.dumps({"type": "history", "messages": recent})
            )
        except Exception:
            pass

    async def disconnect(self, close_code):
        """
        Disconnect from the WebSocket and remove from the group.
        """
        try:
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )
        except Exception:
            pass

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
            saved_meta = await self._save_message(self.event_id, user, message)
        except Exception:
            pass

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
    def _user_is_allowed(self, user, event_id):
        """
        Check if the user is allowed to access the chat for the given event.
        """
        from events.models import Event, EventAttendee

        try:
            event = Event.objects.get(pk=event_id)
        except Event.DoesNotExist:
            return False
        if (
            user
            and getattr(user, "is_authenticated", False)
            and event.host_id == getattr(user, "pk", None)
        ):
            return True
        return EventAttendee.objects.filter(
            event=event, user=user, status="going"
        ).exists()

    @database_sync_to_async
    def _save_message(self, event_id, user, message_text):
        """
        Save a chat message to the database
        and return metadata about the saved message.
        """
        from .models import ChatMessage

        kwargs = {}

        if not (user and getattr(user, "is_authenticated", False)):
            return None
        kwargs["event_id"] = event_id
        kwargs["user_id"] = getattr(user, "pk", None)
        kwargs["content"] = message_text

        msg = ChatMessage.objects.create(**kwargs)

        meta = {"id": getattr(msg, "pk", None)}

        val = getattr(msg, "sent_at")
        meta["timestamp"] = val.isoformat() if val else None

        return meta

    @database_sync_to_async
    def _get_recent_messages(self, event_id, limit=50):
        """
        Retrieve recent chat messages for the given event.
        """
        from .models import ChatMessage

        qs = ChatMessage.objects.filter(event_id=event_id)

        qs = qs.order_by("-pk")[:limit]
        out = []
        for m in reversed(list(qs)):
            u = getattr(m, "user", "anon")
            username = getattr(u, "username", str(u))
            content = getattr(m, "content")
            val = getattr(m, "sent_at")
            ts = val.isoformat() if val else None

            out.append(
                {
                    "username": username,
                    "message": content,
                    "timestamp": ts,
                    "id": getattr(m, "pk", None),
                }
            )
        return out
