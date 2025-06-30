from django.db import models

class Event(models.Model):
    event_id = models.AutoField(primary_key=True)
    host = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=200)
    description = models.TextField()
    datetime = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    location = models.ForeignKey("Location", on_delete=models.SET_NULL, related_name='events', null=True, blank=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['datetime']
        verbose_name_plural = 'Events'

class Location(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postcode = models.CharField(max_length=20)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return f"{self.name}, {self.city}, {self.country}"
    
    class Meta:
        verbose_name_plural = 'Locations'

class EventCategory(models.Model): 
    category_id = models.ForeignKey("Category", on_delete=models.CASCADE, related_name='event_categories')
    event_id = models.ForeignKey("Event", on_delete=models.CASCADE, related_name='event_categories')

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Categories'