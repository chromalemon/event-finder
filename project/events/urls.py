from django.urls import path
from . import views

urlpatterns = [
    path("create/", views.create_event, name="create_event"),
    path("view/", views.view_events, name="view_events"),
    path("view/<int:event_id>/", views.view_event, name="view_event"),
    path("edit/<int:event_id>/", views.edit_event, name="edit_event"),
    path("join/<int:event_id>/", views.join_event, name="join_event"),
]