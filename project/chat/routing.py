from django.urls import path, re_path
from . import consumers

websocket_urlpatterns = [
    path("ws/chat/event/<int:event_id>/", consumers.EventChatConsumer.as_asgi()),
]