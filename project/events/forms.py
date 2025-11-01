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
        fields = ['title', 'description', 'start_time', 'end_time', 'location']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Event Description'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Location'}),
        }

    def clean(self):
        cleaned = super().clean()
        start_time = cleaned.get('start_time')
        end_time = cleaned.get('end_time')
        if start_time and start_time < timezone.now():
            self.add_error('start_time', "Start time cannot be in the past.")
        if start_time and end_time and start_time >= end_time:
            self.add_error('end_time', "End time must be after start time.")
        return cleaned

    def save(self, commit=True, host=None):
        # create/update Event instance, create Location if address provided,
        # attach host and create category relationships
        event = super().save(commit=False)
        if host:
            event.host = host

        addr = self.cleaned_data.get('formatted_address') or None
        lat = self.cleaned_data.get('lat')
        long = self.cleaned_data.get('long')

        if addr and lat is not None and long is not None:
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

            # ensure the host is added as an attendee
            if host:
                EventAttendee.objects.get_or_create(
                    event=event,
                    user=host,
                    defaults={'status': 'going'}
                )

            # categories: create Category and EventCategory relations
            cats = self.cleaned_data.get('categories') or ""
            for name in [c.strip() for c in cats.split(',') if c.strip()]:
                category, _ = Category.objects.get_or_create(name=name)
                EventCategory.objects.get_or_create(cat=category, event=event)
        return event