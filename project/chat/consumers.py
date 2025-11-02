from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
import traceback
from django.utils import timezone

class EventChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for per-event group chat.

    - Avoids importing models at module import time (lazy imports inside DB helpers)
      so ASGI startup doesn't fail with "Apps aren't loaded yet."
    - Dynamically inspects ChatMessage model fields to match your exact schema
      (event FK, user FK, content field, timestamp field).
    - Enforces that only event hosts or attendees with status "going" can connect.
    """
    async def connect(self):
        self.event_id = self.scope['url_route']['kwargs'].get('event_id')
        if not self.event_id:
            await self.close()
            return

        try:
            ok = await self._user_is_allowed(self.scope.get("user"), self.event_id)
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
            await self.send(text_data=json.dumps({"type": "history", "messages": recent}))
        except Exception:
            pass

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    async def receive(self, text_data=None, bytes_data=None):
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
            "username": getattr(user, "username", "anon") if (user and getattr(user, "is_authenticated", False)) else "anon",
        }
        if saved_meta and isinstance(saved_meta, dict):
            payload.update(saved_meta)
        else:
            payload["timestamp"] = timezone.now().isoformat()

        await self.channel_layer.group_send(self.group_name, payload)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "message",
            "message": event.get("message"),
            "username": event.get("username"),
            "timestamp": event.get("timestamp"),
            "id": event.get("id"),
        }))

    @database_sync_to_async
    def _user_is_allowed(self, user, event_id):
        # lazy imports to avoid touching Django models at module import time
        from events.models import Event, EventAttendee
        try:
            event = Event.objects.get(pk=event_id)
        except Event.DoesNotExist:
            return False
        if user and getattr(user, "is_authenticated", False) and event.host_id == getattr(user, "pk", None):
            return True
        return EventAttendee.objects.filter(event=event, user=user, status="going").exists()

    @database_sync_to_async
    def _save_message(self, event_id, user, message_text):
        # Lazy import ChatMessage and Event so this runs only when apps are ready
        from .models import ChatMessage
        from events.models import Event
        from django.contrib.auth import get_user_model

        # Inspect model fields to find the correct field names
        cm_fields = {f.name: f for f in ChatMessage._meta.get_fields()}

        # find event FK field (related_model == Event)
        event_field = None
        for f in ChatMessage._meta.get_fields():
            if getattr(f, "many_to_one", False) and getattr(f, "related_model", None) is Event:
                event_field = f.name
                break
        if not event_field and "event" in cm_fields:
            event_field = "event"

        # find user FK field (related_model == AUTH_USER_MODEL)
        User = get_user_model()
        user_field = None
        for f in ChatMessage._meta.get_fields():
            if getattr(f, "many_to_one", False) and getattr(f, "related_model", None) is User:
                user_field = f.name
                break
        if not user_field:
            for alt in ("user", "sender", "author"):
                if alt in cm_fields:
                    user_field = alt
                    break

        # find content/text field
        content_field = None
        for name, f in cm_fields.items():
            if getattr(f, "concrete", False) and not getattr(f, "is_relation", False):
                it = getattr(f, "get_internal_type", lambda: "")()
                if it in ("TextField", "CharField"):
                    lname = name.lower()
                    if lname not in ("created_at", "created", "updated_at", "timestamp", "sent_at"):
                        content_field = name
                        break
        if not content_field:
            for alt in ("message", "content", "text", "body"):
                if alt in cm_fields:
                    content_field = alt
                    break

        # prepare kwargs for create()
        kwargs = {}
        if event_field:
            kwargs[event_field] = Event.objects.get(pk=event_id)
        else:
            # fallback to event_id if model uses that
            if "event_id" in cm_fields:
                kwargs["event_id"] = event_id

        if user_field:
            kwargs[user_field] = (user if (user and getattr(user, "is_authenticated", False)) else None)

        if content_field:
            kwargs[content_field] = message_text
        else:
            # last resort
            kwargs["message"] = message_text

        msg = ChatMessage.objects.create(**kwargs)

        meta = {"id": getattr(msg, "pk", None)}
        # find timestamp on created message
        for ts_name in ("created_at", "timestamp", "sent_at", "created"):
            if hasattr(msg, ts_name):
                val = getattr(msg, ts_name)
                meta["timestamp"] = val.isoformat() if val else None
                break
        return meta

    @database_sync_to_async
    def _get_recent_messages(self, event_id, limit=50):
        from .models import ChatMessage

        # Determine how to filter by event
        fk_names = [f.name for f in ChatMessage._meta.get_fields() if getattr(f, "many_to_one", False)]
        filter_kwargs = {}
        if "event" in fk_names:
            filter_kwargs["event_id"] = event_id
        else:
            # try common alternatives
            for alt in ("room", "chat", "conversation"):
                if alt in fk_names:
                    filter_kwargs[f"{alt}_id"] = event_id
                    break

        try:
            if filter_kwargs:
                qs = ChatMessage.objects.filter(**filter_kwargs)
            else:
                qs = ChatMessage.objects.filter(event_id=event_id)
        except Exception:
            qs = ChatMessage.objects.none()

        qs = qs.order_by("-pk")[:limit]
        out = []
        for m in reversed(list(qs)):
            username = "anon"
            for uname_field in ("user", "sender", "author"):
                if hasattr(m, uname_field) and getattr(m, uname_field) is not None:
                    u = getattr(m, uname_field)
                    username = getattr(u, "username", str(u))
                    break

            # find content
            content = None
            for content_field in ("message", "content", "text", "body"):
                if hasattr(m, content_field):
                    content = getattr(m, content_field)
                    break
            if content is None:
                for f in ChatMessage._meta.get_fields():
                    if getattr(f, "concrete", False) and not getattr(f, "is_relation", False):
                        it = getattr(f, "get_internal_type", lambda: "")()
                        if it in ("TextField", "CharField"):
                            content = getattr(m, f.name)
                            break

            ts = None
            for ts_name in ("created_at", "timestamp", "sent_at", "created"):
                if hasattr(m, ts_name):
                    val = getattr(m, ts_name)
                    ts = val.isoformat() if val else None
                    break

            out.append({"username": username, "message": content, "timestamp": ts, "id": getattr(m, "pk", None)})
        return out