from django.contrib import admin
from django.urls import path, include
from . import views
from django.shortcuts import redirect

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("events/", include("events.urls")),
    path("chat/", include("chat.urls")),
    path("u/", include("users.urls")),
    path('admin/', admin.site.urls),
    path("", views.home, name="home"),
]


