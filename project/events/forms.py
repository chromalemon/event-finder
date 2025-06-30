from django import forms
from .models import Event
from django.utils import timezone

class EventCreationForm(forms.ModelForm):
    categories = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Categories (comma-separated)'}),
    )
    class Meta:
        model = Event
        fields = ['title', 'description', 'datetime', 'location']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Event Description'}),
            'datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Location'}),
        }
    
    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not title:
            raise forms.ValidationError("Title is required.")
        return title
    
    def clean_date(self):
        datetime = self.cleaned_data.get('datetime')
        if datetime < timezone.now().datetime():
            raise forms.ValidationError("Date cannot be in the past.")
        return datetime