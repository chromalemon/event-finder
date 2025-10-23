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

# Create your views here.


@login_required
def create_event(request):
    if request.method == "POST":
        form = EventCreationForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.host = request.user

            name = request.POST.get('name')
            address = request.POST.get('address')
            city = request.POST.get('city')
            country = request.POST.get('country')
            postcode = request.POST.get('postcode')
            try:
                latitude = float(request.POST.get('latitude'))
                longitude = float(request.POST.get('longitude'))
            except (ValueError, TypeError):
                return render(request, 'events/create_event.html', {
                    'form': form,
                    'error': 'Invalid latitude or longitude.'
                })
            nearby = Location.objects.filter(
                latitude__range=(latitude - 0.01, latitude + 0.01),
                longitude__range=(longitude - 0.01, longitude + 0.01)
            )

            found = None
            for loc in nearby:
                if haversine(latitude, longitude, loc.latitude, loc.longitude) < 0.01:
                    found = loc
                    break
            if found:
                location = found
            else:
                location = Location.objects.create(
                    name=name,
                    address=address,
                    city=city,
                    country=country,
                    postcode=postcode,
                    latitude=latitude,
                    longitude=longitude
                )
            event.location = location
            event.save()
            categories_str = form.cleaned_data.get('categories', '')
            category_names = [name.strip() for name in categories_str.split(',') if name.strip()]
            for cat_name in category_names:
                category_obj, created = Category.objects.get_or_create(name=cat_name)
                EventCategory.objects.create(event=event, category=category_obj)
            return redirect("dashboard")
        else:
            print("Form errors:", form.errors)
            print("Form data:", request.POST)
    else:
        form = EventCreationForm()
    return render(request, 'events/create_event.html', {'form': form})

@login_required
def view_events(request):
    events = Event.objects.select_related("location", "host").prefetch_related("event_categories__category").all()
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
        events = events.filter(event_categories__category__name__in=category_filters).distinct()
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            events = events.filter(datetime__gte=start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            events = events.filter(datetime__lte=end_dt)
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
    return render(request, 'events/view_events.html', context)

    

@login_required
def view_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    return render(request, 'events/view_event.html', {'event': event})

@login_required
def edit_event(request, event_id):
    #edit a specific event
    pass




@login_required
def join_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    if request.method == "POST":
        status = request.POST.get('status', 'interested')
        attendee, created = EventAttendee.objects.get_or_create(event=event, user=request.user)
        attendee.status = status
        attendee.save()
        if created:
            messages.success(request, f"You have joined the event: {event.title} as {status}.")
        else:
            messages.info(request, f"Your status for the event: {event.title} has been updated to {status}.")
        return redirect('view_event', event_id=event_id)
    return render(request, 'events/join_event.html', {'event': event})


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * asin(sqrt(a))
    