from django.urls import path, re_path
from . import consumers

# keep the explicit pattern and add a permissive regex fallback that accepts:
#  - /ws/chat/event/123/
#  - /ws/chat/event/123
#  - /chat/event/123/
#  - /chat/event/123
# This helps when the ASGI router or client URL differ by a prefix or trailing slash.
websocket_urlpatterns = [
    path("ws/chat/event/<int:event_id>/", consumers.EventChatConsumer.as_asgi()),
]