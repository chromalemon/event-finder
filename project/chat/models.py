from django.db import models
from events.models import Event

# Create your models here.



class ChatMessage(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.user_id.username} in chat {self.id}"
