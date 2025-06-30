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
    upcoming_events = (
        Event.objects.filter(host=request.user, datetime__gte=now())
        .order_by('datetime')[:5]
    )
    return render(request, 'event_finder/dashboard.html', {'upcoming_events': upcoming_events})