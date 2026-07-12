from django import forms
from .models import Event, Location, Category, EventCategory, EventAttendee
from django.utils import timezone

class BaseEventForm(forms.ModelForm):
    """
    Form for both event creation and edit.
    """
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
        fields = ['title', 'description', 'start_time', 'end_time', "capacity"]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Event Description'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Event Capacity"}),
        }
    
    def clean(self):
        """
        Validate the provided data.
        """
        cleaned = super().clean()
        start_time = cleaned.get('start_time')
        end_time = cleaned.get('end_time')

        if start_time and start_time < timezone.now():
            self.add_error('start_time', "Start time cannot be in the past.")
        if start_time and end_time and start_time >= end_time:
            self.add_error('end_time', "End time must be after start time.")

        going_count = 0
        if getattr(self.instance, 'pk', None):
            going_count = EventAttendee.objects.filter(event=self.instance, status='going').count()
        capacity = cleaned.get("capacity")
        if capacity is None or capacity < 1:
            self.add_error("capacity", "Capacity must be at least 1.")
        elif capacity < going_count:
            self.add_error("capacity", "Capacity cannot be less than current attendee count.")
        return cleaned
    
    def save(self, commit=True, host=None):
        """
        Create/replace location, assign host if new event, and replace categories before saving to DB.
        """
        event = super().save(commit=False)
        if host:
            event.host = host

        addr = self.cleaned_data.get('formatted_address') or None
        lat = self.cleaned_data.get('lat')
        long = self.cleaned_data.get('long')

        if addr and lat is not None and long is not None:
            try:
                existing_loc = Location.objects.filter(formatted_address=addr, lat=lat, long=long).first()
            except Location.DoesNotExist:
                existing_loc = None

            if existing_loc is not None:
                event.location = existing_loc
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

        else:
            try:
                online_loc = Location.objects.filter(formatted_address="Online", lat=0, long=0).first()
            except Location.DoesNotExist:
                online_loc = None
                
            if online_loc is not None:
                event.location = online_loc
            else:
                loc = Location.objects.create(
                        formatted_address="Online",
                        city=None,
                        country=None,
                        postcode=None,
                        lat=0,
                        long=0,
                    )
                event.location = loc
        
        if commit:
            event.save()

            if host:
                EventAttendee.objects.get_or_create(
                    event=event,
                    user=host,
                    defaults={'status': 'going'}
                )
            
            # replace old categories with new
            EventCategory.objects.filter(event=event).delete()
            cats = self.cleaned_data.get('categories') or ""
            for name in [c.strip() for c in cats.split(',') if c.strip()]:
                category, _ = Category.objects.get_or_create(name=name)
                EventCategory.objects.get_or_create(cat=category, event=event)

        return event