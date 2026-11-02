"""
ASGI config for event_finder project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "event_finder.settings")

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

# Import application modules only after Django has populated the app registry.
import chat.routing
from channels.routing import ProtocolTypeRouter, URLRouter

from chat.middleware import WebSocketAuthTimingMiddleware

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": WebSocketAuthTimingMiddleware(
            URLRouter(chat.routing.websocket_urlpatterns)
        ),
    }
)
