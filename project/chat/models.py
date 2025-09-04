from django.db import models
from events.models import Event

# Create your models here.

class GroupChat(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name='group_chats')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class GroupChatMessage(models.Model):
    chat = models.ForeignKey("GroupChat", on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, related_name='group_chat_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Message from {self.user.username} in chat {self.chat.id}"
