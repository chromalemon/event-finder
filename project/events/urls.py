from django.urls import path
from . import views

app_name = "events"

urlpatterns = [
    path("create/", views.create_event, name="create_event"),
    path("edit/<int:event_id>/", views.edit_event, name="edit_event"),
    path("view/<int:event_id>/", views.view_event, name="view_event"),
    path("join/<int:event_id>/", views.join_event, name="join_event"),
    path("leave/<int:event_id>/", views.leave_event, name="leave_event"),
    path("", views.view_events, name="view_events"),
    path("<int:event_id>/attendee/change/", views.change_attendee_status, name="change_attendee_status"),
]