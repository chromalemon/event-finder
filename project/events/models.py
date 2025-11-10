from django.db import models

class Event(models.Model):
    host = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    location = models.ForeignKey("Location", on_delete=models.SET_NULL, related_name='events', null=True, blank=True)


    def __str__(self):
        return self.title

    class Meta:
        ordering = ['start_time']
        verbose_name_plural = 'Events'

class Location(models.Model):
    formatted_address = models.TextField()
    city = models.CharField(max_length=100, null=True)
    country = models.CharField(max_length=50, null=True)
    postcode = models.CharField(max_length=20, null=True)
    lat = models.FloatField()
    long = models.FloatField()

    def __str__(self):
        return f"{self.formatted_address}"
    
    class Meta:
        verbose_name_plural = 'Locations'

class EventCategory(models.Model): 
    cat = models.ForeignKey("Category", on_delete=models.CASCADE, related_name='event_categories')
    event = models.ForeignKey("Event", on_delete=models.CASCADE, related_name='event_categories')

class Category(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Categories'

class EventAttendee(models.Model):
    '''
    Model to track attendees of an event.
    '''
    event = models.ForeignKey("Event", on_delete=models.CASCADE, related_name='attendees')
    user = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, related_name='attended_events')
    joined_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('going', 'Going'), ('waitlist', 'Waitlisted'), ('not_going', 'Not Going')], default='waitlist')

    class Meta:
        unique_together = ('event', 'user')
        verbose_name_plural = 'Event Attendees'

    def __str__(self):
        return f"{self.user.username} attending {self.event.title}"