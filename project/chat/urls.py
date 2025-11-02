from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path("", views.index, name='index'),                    # /chat/
    path("room/<int:event_id>/", views.chat_room, name="room"),  # /chat/room/123/
]