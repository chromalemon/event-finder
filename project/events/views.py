from django.shortcuts import render, redirect
from django.http import HttpResponse
from .forms import EventCreationForm 
from .models import Event, Location, EventCategory, Category
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from math import radians, cos, sin, asin, sqrt
from django.utils.timezone import now

# Create your views here.

def chat(request):

    return HttpResponse("Hello, world! This is the home page of the events app.")

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
            return redirect("dashboard")
        else:
            print("Form errors:", form.errors)
            print("Form data:", request.POST)
    else:
        form = EventCreationForm()
    return render(request, 'events/create_event.html', {'form': form})
    
def view_events(request):
    #discover events
    pass
def view_event(request, event_id):
    #view a specific event
    pass
def edit_event(request, event_id):
    #edit a specific event
    pass
def view_my_events(request):
    #view events created by the user
    pass



def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * asin(sqrt(a))
    