from django.urls import path
from . import views

urlpatterns = [
    path("", views.empty, name="empty"),
    path("register/", views.register, name='register'),
    path("login/", views.login, name='login'),
    path("logout/", views.logout, name='logout'),
    path("profile/", views.profile, name='profile'),
    path("profile/<int:user_id>/", views.profile, name='profile'),
    path("profile/search/", views.profile_search, name="profile_search"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
]