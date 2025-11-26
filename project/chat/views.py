from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from events.models import Event, EventAttendee
from django.db.models import Q
from django.utils.timezone import now

def index(request):
    """
    Show only event chats that the current user may join:
    - host of the event
    - or attendee with status 'going'
    Anonymous users see an empty list and a prompt to log in.
    """
    user = request.user if request.user.is_authenticated else None

    if not user:
        events = Event.objects.none()
    else:
        events = (
            Event.objects.filter( # Q object allows for boolean logic in queries
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
    Render the chat room page for a specific event. Only allowed if the user
    is the event host or an attendee with status 'going'. If not allowed,
    show an informational page explaining that access is restricted.
    """
    event = get_object_or_404(Event.objects.select_related("host", "location"), pk=event_id)

    # permission: host or going attendee
    is_host = request.user.pk == event.host_id
    is_attendee_going = EventAttendee.objects.filter(event=event, user=request.user, status="going").exists()

    if not (is_host or is_attendee_going):
        return render(request, "chat/forbidden.html", {"event": event})

    # Render chat room UI. The websocket consumer will send recent history on connect.
    return render(request, "chat/room.html", {"event": event})