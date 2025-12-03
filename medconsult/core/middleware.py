from django.utils import timezone

class UserTimezoneMiddleware:
    """
    If the user is authenticated and has a timezone set,
    activate it for the duration of the request.
    Otherwise, fall back to default (settings.TIME_ZONE).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and getattr(user, "timezone", None):
            # e.g. "America/New_York"
            timezone.activate(user.timezone)
        else:
            timezone.deactivate()  # uses default TIME_ZONE (UTC by default)

        response = self.get_response(request)
        return response
