from django.contrib import admin
from django.urls import path, include
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("events/", include(("events.urls", "events"), namespace="events")),
    path("chat/", include(("chat.urls", "chat"), namespace="chat")),
    path("u/", include("users.urls")),
    path('admin/', admin.site.urls),
    path("", views.home, name="home"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Serve static files (including `admin/` assets) when DEBUG=True and
    # the app is run with an ASGI server like `uvicorn` during development.
    urlpatterns += staticfiles_urlpatterns()

