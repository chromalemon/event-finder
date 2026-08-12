from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class LoginRequiredMiddleware:
    """
    Middleware to ensure that the user is logged in
    before accessing certain views.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [
            reverse("home"),
        ]
        if settings.DEBUG:
            self.exempt_urls.append("/admin/")

    def __call__(self, request):
        if not request.user.is_authenticated and not any(
            request.path.startswith(url) for url in self.exempt_urls
        ):
            return redirect("home")
        return self.get_response(request)
