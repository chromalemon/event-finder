from django import forms
from .models import Event, Location, Category, EventCategory, EventAttendee
from django.utils import timezone

class EventCreationForm(forms.ModelForm):
    categories = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Categories (comma-separated)'}),
    )

    # hidden address inputs (the template already posts these)
    formatted_address = forms.CharField(required=False, widget=forms.HiddenInput())
    lat = forms.FloatField(required=False, widget=forms.HiddenInput())
    long = forms.FloatField(required=False, widget=forms.HiddenInput())
    city = forms.CharField(required=False, widget=forms.HiddenInput())
    country = forms.CharField(required=False, widget=forms.HiddenInput())
    postcode = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Event
        # manage Location via hidden inputs, not the FK widget
        fields = ['title', 'description', 'start_time', 'end_time', "capacity"]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Event Description'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Event Capacity"}),
        }

    def clean(self):
        cleaned = super().clean()
        start_time = cleaned.get('start_time')
        end_time = cleaned.get('end_time')
        if start_time and start_time < timezone.now():
            self.add_error('start_time', "Start time cannot be in the past.")
        if start_time and end_time and start_time >= end_time:
            self.add_error('end_time', "End time must be after start time.")
        if cleaned.get("capacity") < 1:
            self.add_error("capacity", "Capacity must be a positive integer.")
        return cleaned

    def save(self, commit=True, host=None):
        """
        On create:
          - create Location if provided and attach it
          - create Event, categories, and EventAttendee(host -> going)

        On update (instance with pk):
          - update existing Location if present, else create
          - update Event fields, replace category relations
        """
        event = super().save(commit=False)
        if host:
            event.host = host

        addr = self.cleaned_data.get('formatted_address') or None
        lat = self.cleaned_data.get('lat')
        long = self.cleaned_data.get('long')

        # handle Location: update existing or create new
        if addr and lat is not None and long is not None:
            if getattr(event, "location", None):
                loc = event.location
                loc.formatted_address = addr
                loc.lat = lat
                loc.long = long
                loc.city = self.cleaned_data.get('city') or None
                loc.country = self.cleaned_data.get('country') or None
                loc.postcode = self.cleaned_data.get('postcode') or None
                loc.save()
                event.location = loc
            else:
                loc = Location.objects.create(
                    formatted_address=addr,
                    city=self.cleaned_data.get('city') or None,
                    country=self.cleaned_data.get('country') or None,
                    postcode=self.cleaned_data.get('postcode') or None,
                    lat=lat,
                    long=long,
                )
                event.location = loc
        # if no address provided and event had an existing location, we leave it unchanged

        if commit:
            event.save()

            # ensure the host is added as an attendee (idempotent)
            if host:
                EventAttendee.objects.get_or_create(
                    event=event,
                    user=host,
                    defaults={'status': 'going'}
                )

            # categories: replace existing relations on edit to avoid duplicates
            EventCategory.objects.filter(event=event).delete()
            cats = self.cleaned_data.get('categories') or ""
            for name in [c.strip() for c in cats.split(',') if c.strip()]:
                category, _ = Category.objects.get_or_create(name=name)
                EventCategory.objects.get_or_create(cat=category, event=event)
        return event

# New: separate form class for editing events
class EventEditForm(forms.ModelForm):
    """
    Form dedicated to editing an existing Event.
    Behaves like EventCreationForm for fields/location/categories,
    but intentionally does NOT assign or modify the event host or create host attendee.
    """
    categories = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Categories (comma-separated)'}),
    )

    formatted_address = forms.CharField(required=False, widget=forms.HiddenInput())
    lat = forms.FloatField(required=False, widget=forms.HiddenInput())
    long = forms.FloatField(required=False, widget=forms.HiddenInput())
    city = forms.CharField(required=False, widget=forms.HiddenInput())
    country = forms.CharField(required=False, widget=forms.HiddenInput())
    postcode = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Event
        fields = ['title', 'description', 'start_time', 'end_time', "capacity"]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Event Description'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Event Capacity"}),
        }

    def clean(self):
        cleaned = super().clean()
        start_time = cleaned.get('start_time')
        end_time = cleaned.get('end_time')
        if start_time and start_time < timezone.now():
            self.add_error('start_time', "Start time cannot be in the past.")
        if start_time and end_time and start_time >= end_time:
            self.add_error('end_time', "End time must be after start time.")

        going_count = EventAttendee.objects.filter(event=self.instance, status='going').count()
        if cleaned.get("capacity") < going_count:
            self.add_error("capacity", "Capacity cannot be less than current attendee count.")
        return cleaned

    def save(self, commit=True):
        """
        Save edits to the event instance. Do not touch host or create host attendee.
        Update or create Location, and replace category relations.
        """
        event = super().save(commit=False)

        addr = self.cleaned_data.get('formatted_address') or None
        lat = self.cleaned_data.get('lat')
        long = self.cleaned_data.get('long')

        if addr and lat is not None and long is not None:
            # update existing location or create new
            if getattr(event, "location", None):
                loc = event.location
                loc.formatted_address = addr
                loc.lat = lat
                loc.long = long
                loc.city = self.cleaned_data.get('city') or None
                loc.country = self.cleaned_data.get('country') or None
                loc.postcode = self.cleaned_data.get('postcode') or None
                loc.save()
                event.location = loc
            else:
                loc = Location.objects.create(
                    formatted_address=addr,
                    city=self.cleaned_data.get('city') or None,
                    country=self.cleaned_data.get('country') or None,
                    postcode=self.cleaned_data.get('postcode') or None,
                    lat=lat,
                    long=long,
                )
                event.location = loc

        if commit:
            event.save()

            # replace categories
            EventCategory.objects.filter(event=event).delete()
            cats = self.cleaned_data.get('categories') or ""
            for name in [c.strip() for c in cats.split(',') if c.strip()]:
                category, _ = Category.objects.get_or_create(name=name)
                EventCategory.objects.get_or_create(cat=category, event=event)
        return event