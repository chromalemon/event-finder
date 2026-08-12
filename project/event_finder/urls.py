from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("events/", include(("events.urls", "events"), namespace="events")),
    path("chat/", include(("chat.urls", "chat"), namespace="chat")),
    path("u/", include("users.urls")),
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
]

handler404 = "event_finder.views.custom_404"
handler500 = "event_finder.views.custom_500"

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
