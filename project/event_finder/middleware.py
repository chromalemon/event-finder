from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings

class LoginRequiredMiddleware:
    """
    Middleware to ensure that the user is logged in before accessing certain views.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [
            reverse('home'),
        ]
        if settings.DEBUG:
            self.exempt_urls.append('/admin/')

    def __call__(self, request):
        if not request.user.is_authenticated:
            if not any(request.path.startswith(url) for url in self.exempt_urls):
                return redirect("home")
        return self.get_response(request)
            