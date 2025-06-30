from django.urls import path
from . import views

urlpatterns = [
    path("create/", views.create_event, name="create_event"),
    path("discover/", views.view_events, name="discover_events"),
    path("view/<int:event_id>/", views.view_event, name="view_event"),
    path("edit/<int:event_id>/", views.edit_event, name="edit_event"),
    path("myevents/", views.view_my_events, name="my_events"),
]