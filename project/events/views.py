from django.shortcuts import render, redirect, get_object_or_404
from .forms import EventCreationForm, EventEditForm
from .models import Event, EventAttendee, Category
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from math import radians, cos, sin, asin, sqrt
from django.utils.timezone import now
from datetime import datetime
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden

# Create your views here.


@login_required
def create_event(request):
    if request.method == "POST":
        form = EventCreationForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=True, host=request.user)
            messages.success(request, "Event created.")
            return redirect('events:view_event', event_id=event.pk)
    else:
        form = EventCreationForm()
    return render(request, "events/create_event.html", {"form": form, "context": "create"})


def view_events(request):
    events = Event.objects.select_related("location", "host").prefetch_related("event_categories__cat").all()
    query = request.GET.get('q', '')
    city_filter = request.GET.get('city', '')
    country_filter = request.GET.get('country', '') 
    category_filters = request.GET.getlist('category')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    sort_order = request.GET.get('sort', 'date_asc')


    if query:
        events = events.filter(title__icontains=query)

    if city_filter:
        events = events.filter(location__city__icontains=city_filter)
    
    if country_filter:
        events = events.filter(location__country__icontains=country_filter)
    
    if category_filters:
        events = events.filter(event_categories__cat__name__in=category_filters).distinct()
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            events = events.filter(start_time__gte=start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            events = events.filter(end_time__lte=end_dt)
        except ValueError:
            pass

    categories = Category.objects.all()
    paginator = Paginator(events, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'events': page_obj,
        'query': query,
        'city_filter': city_filter,
        'country_filter': country_filter,
        'category_filters': category_filters,
        'start_date': start_date,
        'end_date': end_date,
        'categories': categories,
        'sort_order': sort_order,
        'paginator': paginator,
        'page_obj': page_obj,
    }
    return render(request, "events/view_events.html", {
        "events": events,
        "query": query,
        "categories": categories,
        "page_obj": paginator.get_page(page_number),
    })


def view_event(request, event_id):
    """
    Render event detail. If the current user is the event host, include a full
    attendee list (with related user) so the host can manage statuses.
    """
    event = get_object_or_404(Event.objects.select_related("host", "location"), pk=event_id)

    # visitor attendee record (if any)
    user_attendee = None

    # waitlisted users for host (kept as before)
    waitlisted_users = []
    attendees_for_host = []
    if request.user.is_authenticated:
        user_attendee = EventAttendee.objects.filter(event=event, user=request.user).first()
        
    if request.user == event.host:
        qs = EventAttendee.objects.filter(event=event, status="waitlist").select_related("user")
        # order by join timestamp if available, otherwise fallback to pk
        try:
            qs = qs.order_by("joined_at")
        except Exception:
            qs = qs.order_by("pk")
        waitlisted_users = list(qs[:5])

        attendees_for_host = (
            EventAttendee.objects.filter(event=event).select_related("user").order_by("joined_at")
        )

    return render(request, "events/view_event.html", {
        "event": event,
        "user_attendee": user_attendee,
        "waitlisted_users": waitlisted_users,
        "attendees_for_host": attendees_for_host,
    })


@require_POST
@login_required
def change_attendee_status(request, event_id):
    """
    Host-only endpoint to change an attendee's status or remove them.
    Expects POST params:
      - attendee_id: EventAttendee.pk
      - action: one of "set_status" or "remove"
      - status: (when action=="set_status") one of allowed statuses ('going','waitlist','not_going')
    """
    event = get_object_or_404(Event, pk=event_id)
    if request.user != event.host:
        return HttpResponseForbidden("Only the event host can manage attendees.")

    attendee_id = request.POST.get("attendee_id")
    if not attendee_id:
        messages.error(request, "attendee_id missing.")
        return redirect("events:view_event", event_id=event.pk)

    attendee = get_object_or_404(EventAttendee, pk=attendee_id, event=event)

    action = request.POST.get("action") or request.POST.get("status")  # support simple forms
    if action == "remove":
        attendee.delete()
        messages.success(request, f"Removed {attendee.user.username} from the event.")
        return redirect("events:view_event", event_id=event.pk)

    # treat action value as desired status when appropriate
    desired_status = request.POST.get("status") or action
    allowed = {"going", "waitlist", "not_going"}
    if desired_status not in allowed:
        messages.error(request, "Invalid status.")
        return redirect("events:view_event", event_id=event.pk)

    attendee.status = desired_status
    attendee.save()
    messages.success(request, f"Set {attendee.user.username} status to {desired_status}.")
    return redirect("events:view_event", event_id=event.pk)

@login_required
@require_POST
def join_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)

    # check existing attendee record
    try:
        att = EventAttendee.objects.get(event=event, user=request.user)
    except EventAttendee.DoesNotExist:
        att = None

    if att:
        if att.status == "banned":
            messages.error(request, "Access denied.")
            return redirect('events:view_event', event_id=event_id)
        if att.status == "going":
            messages.info(request, "You are already attending this event.")
            return redirect('events:view_event', event_id=event_id)
        if att.status == "waitlist":
            messages.info(request, "You are already on the waitlist for this event.")
            return redirect('events:view_event', event_id=event_id)
        # status == 'not_going' should fall through and attempt to join

    with transaction.atomic():
        locked_event = Event.objects.select_for_update().get(pk=event.pk)
        going_count = EventAttendee.objects.filter(event=locked_event, status='going').count()
        capacity = getattr(locked_event, 'capacity', None)

        if capacity is not None and going_count >= capacity:
            attendee, created = EventAttendee.objects.get_or_create(
                event=locked_event,
                user=request.user,
                defaults={'status': 'waitlist'}
            )
            if not created:
                attendee.status = 'waitlist'
                attendee.save()
            messages.info(request, "The event is full — you've been added to the waitlist.")
        else:
            attendee, created = EventAttendee.objects.get_or_create(
                event=locked_event,
                user=request.user,
                defaults={'status': 'going'}
            )
            if not created:
                attendee.status = 'going'
                attendee.save()
            messages.success(request, "You have joined the event.")

    return redirect('events:view_event', event_id=event_id)

@login_required
@require_POST
def leave_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)

    try:
        attendee = EventAttendee.objects.get(event=event, user=request.user)
    except EventAttendee.DoesNotExist:
        # create a not_going record for idempotence (or simply redirect with message)
        EventAttendee.objects.create(event=event, user=request.user, status='not_going')
        messages.info(request, "You are not listed as attending; marked as not going.")
        return redirect('events:view_event', event_id=event_id)

    # Do not delete record — set status to not_going
    attendee.status = 'not_going'
    attendee.save()
    messages.success(request, "You have left the event.")
    return redirect('events:view_event', event_id=event_id)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * asin(sqrt(a))

def edit_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    if request.user != event.host and not request.user.is_staff:
        messages.error(request, "No permission to edit.")
        return redirect('events:view_event', event_id=event_id)

    initial = {}
    if event.location:
        initial.update({
            "formatted_address": event.location.formatted_address,
            "lat": event.location.lat,
            "long": event.location.long,
            "city": event.location.city,
            "country": event.location.country,
            "postcode": event.location.postcode,
        })
    initial["categories"] = ", ".join(ec.cat.name for ec in event.event_categories.all())

    if request.method == "POST":
        form = EventEditForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save(commit=True)
            messages.success(request, "Event updated.")
            return redirect('events:view_event', event_id=event.pk)
    else:
        form = EventEditForm(instance=event, initial=initial)

    return render(request, "events/create_event.html", {"form": form, "context": "edit", "event": event})