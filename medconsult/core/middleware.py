from django.utils import timezone
from django.conf import settings


class UserTimezoneMiddleware:
    """
    Order:
    1) request.user.timezone
    2) request.session["django_timezone"]
    3) settings.TIME_ZONE
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tz_name = None

        user = getattr(request, "user", None)
        if user and user.is_authenticated and getattr(user, "timezone", None):
            tz_name = user.timezone
        elif "django_timezone" in request.session:
            tz_name = request.session["django_timezone"]
        else:
            tz_name = getattr(settings, "TIME_ZONE", "UTC")

        try:
            timezone.activate(tz_name)
        except Exception:
            timezone.deactivate()

        return self.get_response(request)
