from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from events.models import Event, EventAttendee
from django.db.models import Q

def index(request):
    """
    View for the chat index page. Displays a list of events the user is hosting or attending.
    """
    user = request.user if request.user.is_authenticated else None

    if not user:
        events = Event.objects.none()
    else:
        events = (
            Event.objects.filter(
                Q(host=user) | Q(attendees__user=user, attendees__status="going")
            )
            .select_related("host", "location")
            .distinct()
            .order_by("start_time")
        )

    return render(request, "chat/home.html", {"events": events})

@login_required
def chat_room(request, event_id):
    """
    View for the chat room of a specific event. Only accessible to the event host or attendees with 'going' status.
    """
    event = get_object_or_404(Event.objects.select_related("host", "location"), pk=event_id)

    is_host = request.user.pk == event.host_id
    is_attendee_going = EventAttendee.objects.filter(event=event, user=request.user, status="going").exists()

    if not (is_host or is_attendee_going):
        return render(request, "chat/forbidden.html", {"event": event})

    return render(request, "chat/room.html", {"event": event})