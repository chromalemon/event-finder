from django.shortcuts import render
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from events.models import Event
from django.utils.timezone import now

def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, 'event_finder/home.html')

@login_required
def dashboard(request):
    # only consider attendees with status "going"
    hosted_events = Event.objects.filter(
        host=request.user,
        start_time__gte=now()
    ).order_by('start_time')

    joined_events = (
        Event.objects.filter(
            attendees__user=request.user,
            attendees__status='going',
            start_time__gte=now()
        )
        .exclude(host=request.user)
        .order_by('start_time')
        .distinct()
    )
    if not joined_events.exists():
        messages.info(request, "You haven't joined any events yet. Explore and join some!")
    return render(request, 'event_finder/dashboard.html', {'joined_events': joined_events, "hosted_events": hosted_events})