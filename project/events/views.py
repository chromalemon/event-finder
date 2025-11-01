from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .forms import EventCreationForm 
from .models import Event, Location, EventCategory, Category, EventAttendee
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from math import radians, cos, sin, asin, sqrt
from django.utils.timezone import now
from datetime import datetime
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST

# Create your views here.


@login_required
def create_event(request):
    if request.method == "POST":
        form = EventCreationForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=True, host=request.user)
            return redirect("dashboard")  # adjust to your event detail URL if preferred
    else:
        form = EventCreationForm()
    return render(request, "events/create_event.html", {"form": form, "context": "create"})

@login_required
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

@login_required
def view_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    # attach the current user's attendee record if any so template can show join/leave
    user_attendee = None
    try:
        user_attendee = EventAttendee.objects.get(event=event, user=request.user)
    except EventAttendee.DoesNotExist:
        user_attendee = None

    return render(request, "events/view_event.html", {
        "event": event,
        "user_attendee": user_attendee,
    })

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
            return redirect('view_event', event_id=event_id)
        if att.status == "going":
            messages.info(request, "You are already attending this event.")
            return redirect('view_event', event_id=event_id)
        if att.status == "waitlist":
            messages.info(request, "You are already on the waitlist for this event.")
            return redirect('view_event', event_id=event_id)
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

    return redirect('view_event', event_id=event_id)

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
        return redirect('view_event', event_id=event_id)

    # Do not delete record — set status to not_going
    attendee.status = 'not_going'
    attendee.save()
    messages.success(request, "You have left the event.")
    return redirect('view_event', event_id=event_id)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * asin(sqrt(a))

def edit_event(request, event_id):
    if request.method == "POST":
        form = EventCreationForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=True, host=request.user)
            return redirect("dashboard")  # adjust to your event detail URL if preferred
    else:
        form = EventCreationForm()
    event = Event.objects.get(pk=event_id)
    return render(request, "events/create_event.html", {"form": form, "context": "edit", "event": event})