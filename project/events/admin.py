from django.contrib import admin

from .models import Category, Event, Location

# Register your models here.

admin.site.register(Event)
admin.site.register(Location)
admin.site.register(Category)
